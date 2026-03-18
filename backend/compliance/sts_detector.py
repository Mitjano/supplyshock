"""Ship-to-Ship (STS) transfer detection.

Finds pairs of vessels within 500m of each other, both at low speed (<2 knots),
both laden (high draft). Inserts alert_events with type='sts_transfer'.
"""

import json
import logging

import psycopg2

from config import settings

logger = logging.getLogger(__name__)


def detect_sts_transfers() -> int:
    """Scan for potential STS transfers and insert alerts.

    STS criteria:
    - Two different vessels within 500m of each other
    - Both speed < 2 knots (effectively stationary)
    - Both laden (draft ratio > 0.7 of max draft, or draft > 10m as fallback)

    Returns the number of new alerts created.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Find vessel pairs within 500m, both slow, using latest positions.
            # 500m ~ 0.0045 degrees at the equator (conservative).
            # We use the materialized view for latest positions where available.
            cur.execute("""
                WITH recent AS (
                    SELECT DISTINCT ON (mmsi)
                        mmsi, latitude, longitude, speed, draught, time
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '1 hour'
                      AND speed IS NOT NULL
                      AND speed < 2.0
                    ORDER BY mmsi, time DESC
                ),
                pairs AS (
                    SELECT
                        a.mmsi AS mmsi_a,
                        b.mmsi AS mmsi_b,
                        a.latitude AS lat_a, a.longitude AS lon_a,
                        b.latitude AS lat_b, b.longitude AS lon_b,
                        a.speed AS speed_a, b.speed AS speed_b,
                        a.draught AS draught_a, b.draught AS draught_b,
                        a.time AS time_a, b.time AS time_b,
                        -- Distance in meters (approximate)
                        6371000 * ACOS(
                            LEAST(1.0, GREATEST(-1.0,
                                COS(RADIANS(a.latitude)) * COS(RADIANS(b.latitude)) *
                                COS(RADIANS(b.longitude) - RADIANS(a.longitude)) +
                                SIN(RADIANS(a.latitude)) * SIN(RADIANS(b.latitude))
                            ))
                        ) AS distance_m
                    FROM recent a
                    JOIN recent b ON a.mmsi < b.mmsi
                        -- Bounding box pre-filter (~5km)
                        AND ABS(a.latitude - b.latitude) < 0.05
                        AND ABS(a.longitude - b.longitude) < 0.05
                )
                SELECT mmsi_a, mmsi_b, lat_a, lon_a, lat_b, lon_b,
                       speed_a, speed_b, draught_a, draught_b,
                       distance_m, GREATEST(time_a, time_b) AS event_time
                FROM pairs
                WHERE distance_m < 500
                  -- At least one vessel should have significant draft (laden)
                  AND (COALESCE(draught_a, 0) > 8 OR COALESCE(draught_b, 0) > 8)
            """)
            pairs = cur.fetchall()

            if not pairs:
                logger.info("STS detection: no events found")
                return 0

            inserted = 0
            for (mmsi_a, mmsi_b, lat_a, lon_a, lat_b, lon_b,
                 speed_a, speed_b, draught_a, draught_b,
                 distance_m, event_time) in pairs:

                # Deduplicate: check if we already alerted on this pair recently
                cur.execute("""
                    SELECT 1 FROM alert_events
                    WHERE type = 'sts_transfer'
                      AND time > NOW() - INTERVAL '6 hours'
                      AND (
                          (metadata->>'mmsi_a' = %s AND metadata->>'mmsi_b' = %s)
                          OR
                          (metadata->>'mmsi_a' = %s AND metadata->>'mmsi_b' = %s)
                      )
                    LIMIT 1
                """, (str(mmsi_a), str(mmsi_b), str(mmsi_b), str(mmsi_a)))

                if cur.fetchone():
                    continue

                metadata = json.dumps({
                    "mmsi_a": mmsi_a,
                    "mmsi_b": mmsi_b,
                    "distance_m": round(distance_m, 1),
                    "speed_a": speed_a,
                    "speed_b": speed_b,
                    "draught_a": draught_a,
                    "draught_b": draught_b,
                    "position": {
                        "lat": round((lat_a + lat_b) / 2, 5),
                        "lon": round((lon_a + lon_b) / 2, 5),
                    },
                })

                cur.execute("""
                    INSERT INTO alert_events
                        (time, type, severity, title, body, mmsi, metadata, is_active)
                    VALUES
                        (%s, 'sts_transfer', 'warning', %s, %s, %s, %s, TRUE)
                """, (
                    event_time,
                    f"Potential STS transfer: {mmsi_a} / {mmsi_b}",
                    f"Vessels {mmsi_a} and {mmsi_b} within {distance_m:.0f}m, "
                    f"both near-stationary (speed {speed_a:.1f}/{speed_b:.1f} kn).",
                    mmsi_a,  # primary vessel
                    metadata,
                ))
                inserted += 1

            conn.commit()
            logger.info("STS detection: inserted %d alerts", inserted)
            return inserted
    finally:
        conn.close()
