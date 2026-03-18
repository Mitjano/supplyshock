"""AIS spoofing detection.

Detects two spoofing indicators:
1. Teleportation — position jumps >100 km in <1 hour
2. Impossible speed — >35 knots for cargo/tanker vessels

Inserts alert_events with type='ais_spoofing'.
"""

import json
import logging

import psycopg2

from config import settings

logger = logging.getLogger(__name__)

# Vessel type codes (AIS) for cargo and tankers — these should not exceed ~25 kn
CARGO_TANKER_TYPES = (70, 71, 72, 73, 74, 75, 76, 77, 78, 79,  # cargo
                      80, 81, 82, 83, 84, 85, 86, 87, 88, 89)  # tanker


def detect_ais_spoofing() -> int:
    """Scan for AIS spoofing indicators and insert alerts.

    Returns the number of new alerts created.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        inserted = 0
        with conn.cursor() as cur:
            inserted += _detect_teleportation(cur)
            inserted += _detect_impossible_speed(cur)

        conn.commit()
        logger.info("AIS spoofing detection: inserted %d alerts", inserted)
        return inserted
    finally:
        conn.close()


def _detect_teleportation(cur) -> int:
    """Detect position jumps >100 km in <1 hour."""
    cur.execute("""
        WITH ordered AS (
            SELECT
                mmsi,
                time,
                latitude,
                longitude,
                LAG(time) OVER (PARTITION BY mmsi ORDER BY time) AS prev_time,
                LAG(latitude) OVER (PARTITION BY mmsi ORDER BY time) AS prev_lat,
                LAG(longitude) OVER (PARTITION BY mmsi ORDER BY time) AS prev_lon
            FROM vessel_positions
            WHERE time > NOW() - INTERVAL '2 hours'
        ),
        jumps AS (
            SELECT
                mmsi,
                prev_time,
                time AS jump_time,
                EXTRACT(EPOCH FROM (time - prev_time)) / 3600.0 AS hours_diff,
                prev_lat, prev_lon,
                latitude AS new_lat, longitude AS new_lon,
                6371 * ACOS(
                    LEAST(1.0, GREATEST(-1.0,
                        COS(RADIANS(prev_lat)) * COS(RADIANS(latitude)) *
                        COS(RADIANS(longitude) - RADIANS(prev_lon)) +
                        SIN(RADIANS(prev_lat)) * SIN(RADIANS(latitude))
                    ))
                ) AS distance_km
            FROM ordered
            WHERE prev_time IS NOT NULL
              AND EXTRACT(EPOCH FROM (time - prev_time)) > 0
              AND EXTRACT(EPOCH FROM (time - prev_time)) < 3600
        )
        SELECT mmsi, prev_time, jump_time, hours_diff, distance_km,
               prev_lat, prev_lon, new_lat, new_lon
        FROM jumps
        WHERE distance_km > 100
        ORDER BY distance_km DESC
        LIMIT 100
    """)
    jumps = cur.fetchall()

    inserted = 0
    for (mmsi, prev_time, jump_time, hours_diff, distance_km,
         prev_lat, prev_lon, new_lat, new_lon) in jumps:

        # Deduplicate
        cur.execute("""
            SELECT 1 FROM alert_events
            WHERE type = 'ais_spoofing'
              AND mmsi = %s
              AND time > %s - INTERVAL '2 hours'
              AND metadata->>'subtype' = 'teleportation'
            LIMIT 1
        """, (mmsi, jump_time))

        if cur.fetchone():
            continue

        implied_speed = distance_km / max(hours_diff, 0.01)
        severity = "critical" if distance_km > 500 else "warning"

        metadata = json.dumps({
            "subtype": "teleportation",
            "distance_km": round(distance_km, 1),
            "hours_diff": round(hours_diff, 3),
            "implied_speed_kn": round(implied_speed / 1.852, 1),
            "from": {"lat": prev_lat, "lon": prev_lon, "time": prev_time.isoformat()},
            "to": {"lat": new_lat, "lon": new_lon, "time": jump_time.isoformat()},
        })

        cur.execute("""
            INSERT INTO alert_events
                (time, type, severity, title, body, mmsi, metadata, is_active)
            VALUES
                (%s, 'ais_spoofing', %s, %s, %s, %s, %s, TRUE)
        """, (
            jump_time,
            severity,
            f"AIS spoofing (teleportation): MMSI {mmsi}",
            f"Vessel {mmsi} jumped {distance_km:.0f} km in {hours_diff * 60:.0f} min "
            f"(implied {implied_speed / 1.852:.0f} kn).",
            mmsi,
            metadata,
        ))
        inserted += 1

    return inserted


def _detect_impossible_speed(cur) -> int:
    """Detect cargo/tanker vessels reporting speed >35 knots."""
    cur.execute("""
        SELECT DISTINCT ON (vp.mmsi)
            vp.mmsi, vp.speed, vp.time, vp.latitude, vp.longitude,
            v.ship_type
        FROM vessel_positions vp
        JOIN vessels v ON v.mmsi = vp.mmsi
        WHERE vp.time > NOW() - INTERVAL '30 minutes'
          AND vp.speed > 35
          AND v.ship_type IN %s
        ORDER BY vp.mmsi, vp.time DESC
    """, (CARGO_TANKER_TYPES,))
    rows = cur.fetchall()

    inserted = 0
    for mmsi, speed, time, lat, lon, ship_type in rows:

        # Deduplicate
        cur.execute("""
            SELECT 1 FROM alert_events
            WHERE type = 'ais_spoofing'
              AND mmsi = %s
              AND time > %s - INTERVAL '1 hour'
              AND metadata->>'subtype' = 'impossible_speed'
            LIMIT 1
        """, (mmsi, time))

        if cur.fetchone():
            continue

        metadata = json.dumps({
            "subtype": "impossible_speed",
            "reported_speed_kn": speed,
            "ship_type": ship_type,
            "position": {"lat": lat, "lon": lon},
        })

        cur.execute("""
            INSERT INTO alert_events
                (time, type, severity, title, body, mmsi, metadata, is_active)
            VALUES
                (%s, 'ais_spoofing', 'warning', %s, %s, %s, %s, TRUE)
        """, (
            time,
            f"AIS spoofing (impossible speed): MMSI {mmsi}",
            f"Cargo/tanker vessel {mmsi} reporting {speed:.1f} kn "
            f"(ship_type={ship_type}, max realistic ~25 kn).",
            mmsi,
            metadata,
        ))
        inserted += 1

    return inserted
