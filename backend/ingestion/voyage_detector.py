"""Voyage detection, floating storage, and trade flow enrichment.

Issue #41: Detects port enter/exit events by comparing vessel positions
against port geofences. Creates/closes voyage records.

Issue #43: Floating storage detection — laden vessels stationary >7 days
outside port geofences get flagged as floating_storage.

Issue #44: Trade flow enrichment — on voyage arrival, links voyage data
to trade_flows table (creates or updates live flow records).

State tracking: Redis key `vessel:{mmsi}:last_port` stores the port_id
of the last known port for each vessel.

Run as Celery Beat tasks: detect_voyages every 5 min, detect_floating_storage every 1h.
"""

import json
import logging
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import redis

from config import settings

logger = logging.getLogger(__name__)

# Redis key TTL — 7 days (vessels not seen for 7d get re-evaluated)
REDIS_KEY_TTL = 7 * 24 * 3600

# Minimum speed to consider vessel "underway" (knots)
MIN_UNDERWAY_SPEED = 1.0

# Floating storage thresholds
FLOATING_STORAGE_DAYS = 7      # must be stationary for >7 days
FLOATING_STORAGE_SPEED = 0.5   # max speed (knots) to be considered stationary
FLOATING_STORAGE_DRIFT = 0.01  # max lat/lon drift (degrees, ~1.1 km)

# Laden/ballast classification thresholds
LADEN_DRAUGHT_RATIO = 0.6  # current_draught > 0.6 × max_draught → laden

# Load factors for volume estimation
LOAD_FACTORS = {
    "tanker": 0.95,
    "bulk_carrier": 0.90,
    "container": 0.80,
    "lng_carrier": 0.92,
    "general_cargo": 0.85,
    "other": 0.85,
}


def _get_redis():
    return redis.from_url(settings.REDIS_URL)


def _classify_laden(current_draught: float | None, max_draught: float | None) -> str:
    """Classify vessel as laden or ballast based on draught ratio."""
    if not current_draught or not max_draught or max_draught <= 0:
        return "unknown"
    ratio = current_draught / max_draught
    return "laden" if ratio > LADEN_DRAUGHT_RATIO else "ballast"


def _estimate_volume(
    dwt_estimate: float | None,
    current_draught: float | None,
    max_draught: float | None,
    vessel_type: str,
) -> float | None:
    """Estimate cargo volume in metric tonnes.

    Formula: dwt × (current_draught / max_draught) × load_factor
    """
    if not all([dwt_estimate, current_draught, max_draught]):
        return None
    if max_draught <= 0 or dwt_estimate <= 0:
        return None
    load_factor = LOAD_FACTORS.get(vessel_type, 0.85)
    ratio = min(current_draught / max_draught, 1.0)
    return round(dwt_estimate * ratio * load_factor, 2)


def _infer_cargo_type(port_commodities: list[str] | None) -> str | None:
    """Infer cargo type from origin port's commodity list.

    Returns the first commodity (most prominent) or None.
    """
    if not port_commodities:
        return None
    return port_commodities[0]


def _enrich_trade_flow(cur, voyage_id: str) -> None:
    """Link a completed voyage to trade_flows (Issue #44).

    On voyage arrival:
    - Match origin_port country → dest_port country + cargo_type
    - If matching trade_flow exists for current month: add volume
    - If no match: create new trade_flow with source='live'
    """
    cur.execute("""
        SELECT v.cargo_type, v.volume_estimate,
               op.country_code AS origin_country,
               dp.country_code AS dest_country,
               v.origin_port_id, v.dest_port_id
        FROM voyages v
        LEFT JOIN ports op ON op.id = v.origin_port_id
        LEFT JOIN ports dp ON dp.id = v.dest_port_id
        WHERE v.id = %s
    """, (voyage_id,))
    row = cur.fetchone()

    if not row or not row["cargo_type"] or not row["volume_estimate"]:
        return
    if not row["origin_country"] or not row["dest_country"]:
        return

    now = datetime.now(timezone.utc)

    # Try to update existing trade_flow for this route/commodity/month
    cur.execute("""
        UPDATE trade_flows SET
            volume_mt = COALESCE(volume_mt, 0) + %s,
            updated_at = NOW()
        WHERE commodity = %s
          AND origin_country = %s
          AND destination_country = %s
          AND period_year = %s
          AND period_month = %s
          AND source = 'live'
    """, (
        row["volume_estimate"],
        row["cargo_type"],
        row["origin_country"],
        row["dest_country"],
        now.year,
        now.month,
    ))

    if cur.rowcount == 0:
        # No existing flow — create new one
        cur.execute("""
            INSERT INTO trade_flows (
                commodity, origin_country, destination_country,
                origin_port_id, destination_port_id,
                volume_mt, period_year, period_month, source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'live')
        """, (
            row["cargo_type"],
            row["origin_country"],
            row["dest_country"],
            row["origin_port_id"],
            row["dest_port_id"],
            row["volume_estimate"],
            now.year,
            now.month,
        ))


def detect_voyages():
    """Main voyage detection logic — called by Celery Beat every 5 minutes.

    Algorithm:
    1. Get all vessels with positions in last 10 minutes
    2. For each vessel, check if it's in a port (PostGIS is_in_port)
    3. Compare with last known state (Redis vessel:{mmsi}:last_port)
    4. If state changed: create/close voyage + enrich trade flows
    """
    r = _get_redis()
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)

    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get recent vessel positions (one per MMSI, last 10 minutes)
        cur.execute("""
            SELECT DISTINCT ON (vp.mmsi)
                vp.mmsi, vp.imo, vp.vessel_name, vp.vessel_type,
                vp.latitude, vp.longitude, vp.speed_knots, vp.draught,
                vp.time,
                vs.max_draught, vs.dwt_estimate
            FROM vessel_positions vp
            LEFT JOIN vessel_static_data vs ON vs.mmsi = vp.mmsi
            WHERE vp.time > NOW() - INTERVAL '10 minutes'
            ORDER BY vp.mmsi, vp.time DESC
        """)
        vessels = cur.fetchall()

        if not vessels:
            logger.debug("No vessel positions in last 10 minutes")
            conn.rollback()
            return

        new_voyages = 0
        closed_voyages = 0

        for v in vessels:
            mmsi = v["mmsi"]
            lat = v["latitude"]
            lon = v["longitude"]

            # Check if vessel is in a port
            cur.execute(
                "SELECT port_id, port_name, distance_km FROM is_in_port(%s, %s)",
                (lat, lon),
            )
            port_row = cur.fetchone()
            current_port_id = str(port_row["port_id"]) if port_row else None

            # Get last known port from Redis
            redis_key = f"vessel:{mmsi}:last_port"
            last_state_raw = r.get(redis_key)
            last_port_id = None
            if last_state_raw:
                try:
                    last_state = json.loads(last_state_raw)
                    last_port_id = last_state.get("port_id")
                except (json.JSONDecodeError, TypeError):
                    pass

            # --- State transitions ---

            if last_port_id and not current_port_id:
                # DEPARTURE: was in port, now at sea → create new voyage
                speed = float(v["speed_knots"]) if v["speed_knots"] else 0
                if speed < MIN_UNDERWAY_SPEED:
                    # Vessel might be anchored outside port, skip
                    continue

                # Get origin port commodities for cargo inference
                cur.execute(
                    "SELECT commodities FROM ports WHERE id = %s",
                    (last_port_id,),
                )
                origin_port = cur.fetchone()
                cargo_type = _infer_cargo_type(
                    origin_port["commodities"] if origin_port else None
                )

                laden_status = _classify_laden(
                    float(v["draught"]) if v["draught"] else None,
                    float(v["max_draught"]) if v["max_draught"] else None,
                )

                volume_estimate = _estimate_volume(
                    float(v["dwt_estimate"]) if v["dwt_estimate"] else None,
                    float(v["draught"]) if v["draught"] else None,
                    float(v["max_draught"]) if v["max_draught"] else None,
                    v["vessel_type"],
                )

                cur.execute("""
                    INSERT INTO voyages (
                        mmsi, imo, vessel_name, vessel_type,
                        origin_port_id, departure_time, status,
                        laden_status, cargo_type, volume_estimate
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'underway', %s, %s, %s)
                """, (
                    mmsi, v["imo"], v["vessel_name"], v["vessel_type"],
                    last_port_id, v["time"],
                    laden_status, cargo_type, volume_estimate,
                ))
                new_voyages += 1

                # Clear port state in Redis
                r.delete(redis_key)

            elif not last_port_id and current_port_id:
                # ARRIVAL: was at sea, now in port → close active voyage
                cur.execute("""
                    UPDATE voyages SET
                        dest_port_id = %s,
                        arrival_time = %s,
                        status = 'arrived'
                    WHERE id = (
                        SELECT id FROM voyages
                        WHERE mmsi = %s AND status = 'underway'
                        ORDER BY departure_time DESC
                        LIMIT 1
                    )
                    RETURNING id
                """, (current_port_id, v["time"], mmsi))

                arrival_row = cur.fetchone()
                if arrival_row:
                    closed_voyages += 1
                    # Enrich trade flows with voyage data (#44)
                    try:
                        _enrich_trade_flow(cur, str(arrival_row["id"]))
                    except Exception as e:
                        logger.warning("Trade flow enrichment failed for voyage %s: %s",
                                       arrival_row["id"], e)
                else:
                    logger.debug("MMSI %d arrived at port %s but no active voyage found",
                                 mmsi, port_row["port_name"])

                # Store current port in Redis
                r.setex(
                    redis_key,
                    REDIS_KEY_TTL,
                    json.dumps({
                        "port_id": current_port_id,
                        "port_name": port_row["port_name"],
                        "arrived_at": datetime.now(timezone.utc).isoformat(),
                    }),
                )

            elif current_port_id and current_port_id != last_port_id:
                # PORT CHANGE: was in port A, now in port B (e.g. nearby ports)
                # Close any active voyage, update Redis
                cur.execute("""
                    UPDATE voyages SET
                        dest_port_id = %s,
                        arrival_time = %s,
                        status = 'arrived'
                    WHERE id = (
                        SELECT id FROM voyages
                        WHERE mmsi = %s AND status = 'underway'
                        ORDER BY departure_time DESC
                        LIMIT 1
                    )
                    RETURNING id
                """, (current_port_id, v["time"], mmsi))

                arrival_row = cur.fetchone()
                if arrival_row:
                    closed_voyages += 1
                    try:
                        _enrich_trade_flow(cur, str(arrival_row["id"]))
                    except Exception as e:
                        logger.warning("Trade flow enrichment failed for voyage %s: %s",
                                       arrival_row["id"], e)

                r.setex(
                    redis_key,
                    REDIS_KEY_TTL,
                    json.dumps({
                        "port_id": current_port_id,
                        "port_name": port_row["port_name"],
                        "arrived_at": datetime.now(timezone.utc).isoformat(),
                    }),
                )

            elif current_port_id and current_port_id == last_port_id:
                # STILL IN PORT: refresh Redis TTL
                r.expire(redis_key, REDIS_KEY_TTL)

            # If not in port and no last_port → vessel is underway, no action needed

        conn.commit()

        if new_voyages or closed_voyages:
            logger.info(
                "Voyage detection: %d departures, %d arrivals (from %d vessels)",
                new_voyages, closed_voyages, len(vessels),
            )

    except Exception as e:
        conn.rollback()
        logger.error("Voyage detection failed: %s", e, exc_info=True)
        raise
    finally:
        conn.close()


def detect_floating_storage():
    """Detect floating storage — called by Celery Beat every 1 hour.

    Finds laden vessels that have been stationary (speed <0.5 knot, drift <0.01°)
    for >7 days outside any port geofence. Updates voyage status to 'floating_storage'
    and creates an alert.

    Issue #43.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)

    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Find underway voyages with laden status where vessel has been
        # nearly stationary for >7 days outside any port
        cur.execute("""
            WITH stationary_vessels AS (
                SELECT
                    vp.mmsi,
                    MIN(vp.time) AS first_seen,
                    MAX(vp.time) AS last_seen,
                    AVG(vp.latitude) AS avg_lat,
                    AVG(vp.longitude) AS avg_lon,
                    MAX(vp.latitude) - MIN(vp.latitude) AS lat_drift,
                    MAX(vp.longitude) - MIN(vp.longitude) AS lon_drift,
                    AVG(vp.speed_knots) AS avg_speed
                FROM vessel_positions vp
                WHERE vp.time > NOW() - INTERVAL '%s days'
                GROUP BY vp.mmsi
                HAVING
                    AVG(vp.speed_knots) < %s
                    AND (MAX(vp.latitude) - MIN(vp.latitude)) < %s
                    AND (MAX(vp.longitude) - MIN(vp.longitude)) < %s
                    AND EXTRACT(EPOCH FROM MAX(vp.time) - MIN(vp.time)) > %s * 86400
            )
            SELECT
                sv.mmsi, sv.avg_lat, sv.avg_lon, sv.first_seen, sv.last_seen,
                sv.avg_speed, sv.lat_drift, sv.lon_drift,
                v.id AS voyage_id, v.vessel_name, v.cargo_type, v.volume_estimate
            FROM stationary_vessels sv
            JOIN voyages v ON v.mmsi = sv.mmsi AND v.status = 'underway'
            WHERE v.laden_status = 'laden'
              AND NOT EXISTS (
                  SELECT 1 FROM is_in_port(sv.avg_lat, sv.avg_lon)
              )
        """, (
            FLOATING_STORAGE_DAYS + 1,  # look back window
            FLOATING_STORAGE_SPEED,
            FLOATING_STORAGE_DRIFT,
            FLOATING_STORAGE_DRIFT,
            FLOATING_STORAGE_DAYS,
        ))

        candidates = cur.fetchall()
        converted = 0

        for c in candidates:
            # Update voyage status
            cur.execute("""
                UPDATE voyages SET status = 'floating_storage'
                WHERE id = %s AND status = 'underway'
            """, (c["voyage_id"],))

            if cur.rowcount > 0:
                converted += 1

                # Create alert
                cur.execute("""
                    INSERT INTO alert_events (
                        type, severity, title, body,
                        commodity, mmsi, source, metadata
                    ) VALUES (
                        'ais_anomaly', 'warning',
                        %s, %s, %s, %s, 'floating_storage',
                        %s::jsonb
                    )
                """, (
                    f"Floating storage detected: {c['vessel_name'] or 'MMSI ' + str(c['mmsi'])}",
                    f"Vessel stationary for >{FLOATING_STORAGE_DAYS} days at "
                    f"({c['avg_lat']:.2f}, {c['avg_lon']:.2f}), "
                    f"laden with {c['cargo_type'] or 'unknown cargo'}. "
                    f"Estimated volume: {c['volume_estimate'] or 'N/A'} MT.",
                    c["cargo_type"],
                    c["mmsi"],
                    json.dumps({
                        "voyage_id": str(c["voyage_id"]),
                        "latitude": float(c["avg_lat"]),
                        "longitude": float(c["avg_lon"]),
                        "days_stationary": round(
                            (c["last_seen"] - c["first_seen"]).total_seconds() / 86400, 1
                        ),
                        "avg_speed": round(float(c["avg_speed"]), 2),
                        "volume_estimate": float(c["volume_estimate"]) if c["volume_estimate"] else None,
                    }),
                ))

        conn.commit()

        if converted:
            logger.info("Floating storage: %d vessels flagged (from %d candidates)",
                         converted, len(candidates))

    except Exception as e:
        conn.rollback()
        logger.error("Floating storage detection failed: %s", e, exc_info=True)
        raise
    finally:
        conn.close()
