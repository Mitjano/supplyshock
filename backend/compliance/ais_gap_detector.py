"""AIS gap detection.

Finds vessels that had positions, disappeared for >6 hours,
and reappeared >50 km away. Inserts alert_events with type='ais_gap'.
"""

import json
import logging
from datetime import datetime, timezone

import psycopg2

from config import settings

logger = logging.getLogger(__name__)


def detect_ais_gaps() -> int:
    """Scan for AIS gaps and insert alerts.

    An AIS gap is defined as:
    - A vessel had a position report
    - No reports for > 6 hours
    - Next report is > 50 km from the last known position

    Returns the number of new alerts created.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Find consecutive position pairs per vessel where the time gap > 6h
            # and distance > 50km, looking at the last 24h of data.
            # Uses LEAD() window function to compare consecutive positions.
            cur.execute("""
                WITH ordered_positions AS (
                    SELECT
                        mmsi,
                        time,
                        latitude,
                        longitude,
                        LEAD(time) OVER (PARTITION BY mmsi ORDER BY time) AS next_time,
                        LEAD(latitude) OVER (PARTITION BY mmsi ORDER BY time) AS next_lat,
                        LEAD(longitude) OVER (PARTITION BY mmsi ORDER BY time) AS next_lon
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '48 hours'
                ),
                gaps AS (
                    SELECT
                        mmsi,
                        time AS gap_start,
                        next_time AS gap_end,
                        EXTRACT(EPOCH FROM (next_time - time)) / 3600.0 AS gap_hours,
                        latitude AS last_lat,
                        longitude AS last_lon,
                        next_lat AS reappear_lat,
                        next_lon AS reappear_lon,
                        -- Haversine distance in km
                        6371 * ACOS(
                            LEAST(1.0, GREATEST(-1.0,
                                COS(RADIANS(latitude)) * COS(RADIANS(next_lat)) *
                                COS(RADIANS(next_lon) - RADIANS(longitude)) +
                                SIN(RADIANS(latitude)) * SIN(RADIANS(next_lat))
                            ))
                        ) AS distance_km
                    FROM ordered_positions
                    WHERE next_time IS NOT NULL
                      AND EXTRACT(EPOCH FROM (next_time - time)) > 6 * 3600
                )
                SELECT mmsi, gap_start, gap_end, gap_hours, distance_km,
                       last_lat, last_lon, reappear_lat, reappear_lon
                FROM gaps
                WHERE distance_km > 50
                  -- Only gaps that ended in the last 2 hours (avoid re-alerting)
                  AND gap_end > NOW() - INTERVAL '2 hours'
                ORDER BY gap_hours DESC
            """)
            gaps = cur.fetchall()

            if not gaps:
                logger.info("AIS gap detection: no new gaps found")
                return 0

            inserted = 0
            for mmsi, gap_start, gap_end, gap_hours, distance_km, \
                    last_lat, last_lon, reappear_lat, reappear_lon in gaps:

                # Check if we already have an alert for this gap
                cur.execute("""
                    SELECT 1 FROM alert_events
                    WHERE type = 'ais_gap'
                      AND mmsi = %s
                      AND time BETWEEN %s - INTERVAL '1 hour' AND %s + INTERVAL '1 hour'
                    LIMIT 1
                """, (mmsi, gap_start, gap_start))

                if cur.fetchone():
                    continue

                severity = "critical" if gap_hours > 24 or distance_km > 200 else "warning"

                metadata = json.dumps({
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                    "gap_hours": round(gap_hours, 1),
                    "distance_km": round(distance_km, 1),
                    "last_position": {"lat": last_lat, "lon": last_lon},
                    "reappear_position": {"lat": reappear_lat, "lon": reappear_lon},
                })

                cur.execute("""
                    INSERT INTO alert_events
                        (time, type, severity, title, body, mmsi, metadata, is_active)
                    VALUES
                        (%s, 'ais_gap', %s, %s, %s, %s, %s, TRUE)
                """, (
                    gap_end,
                    severity,
                    f"AIS gap detected: MMSI {mmsi}",
                    f"Vessel {mmsi} went dark for {gap_hours:.1f}h and reappeared "
                    f"{distance_km:.0f} km away.",
                    mmsi,
                    metadata,
                ))
                inserted += 1

            conn.commit()
            logger.info("AIS gap detection: inserted %d alerts", inserted)
            return inserted
    finally:
        conn.close()
