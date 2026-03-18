"""Port analytics — dwell time, turnaround, queue length, throughput.

Calculates per-port performance metrics from voyages and vessel_positions data.
Called by Celery beat task `calculate_port_analytics` every 1h.
"""

import logging
from datetime import datetime, timezone

import psycopg2

from config import settings

logger = logging.getLogger("port_analytics")


def _ensure_table(conn):
    """Create port_analytics table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS port_analytics (
                id BIGSERIAL PRIMARY KEY,
                port_id UUID NOT NULL,
                period_start TIMESTAMPTZ NOT NULL,
                period_end TIMESTAMPTZ NOT NULL,
                dwell_time_median_hours DOUBLE PRECISION,
                turnaround_hours DOUBLE PRECISION,
                queue_length INT DEFAULT 0,
                throughput_vessels INT DEFAULT 0,
                vessel_count INT DEFAULT 0,
                avg_wait_hours DOUBLE PRECISION,
                calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (port_id, period_start)
            )
        """)
    conn.commit()


def calculate_all_port_analytics(period_days: int = 30) -> dict:
    """Calculate analytics for all major ports and store results.

    Queries voyages and vessel_positions to compute:
    - dwell_time_median: median time vessels spend in port
    - turnaround: avg time from arrival to departure
    - queue_length: vessels currently waiting (speed < 1 knot near port)
    - throughput: total vessels that visited in the period
    - vessel_count: vessels currently in port
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        ports_processed = 0

        with conn.cursor() as cur:
            # Get all major ports
            cur.execute("SELECT id, latitude, longitude, radius_km FROM ports WHERE is_major = true")
            ports = cur.fetchall()

            now = datetime.now(timezone.utc)

            for port_id, lat, lon, radius_km in ports:
                radius = radius_km or 5.0

                try:
                    # Throughput: count distinct vessels that visited (arrived at) this port
                    cur.execute("""
                        SELECT COUNT(DISTINCT v.mmsi) as throughput,
                               COUNT(*) as voyage_count
                        FROM voyages v
                        WHERE v.destination_port_id = %s
                          AND v.arrival_time > NOW() - INTERVAL '%s days'
                          AND v.arrival_time IS NOT NULL
                    """, (str(port_id), period_days))
                    throughput_row = cur.fetchone()
                    throughput = throughput_row[0] if throughput_row else 0

                    # Dwell time and turnaround from voyages
                    cur.execute("""
                        SELECT
                            PERCENTILE_CONT(0.5) WITHIN GROUP (
                                ORDER BY EXTRACT(EPOCH FROM (v.departure_time - v.arrival_time)) / 3600
                            ) as dwell_median_hours,
                            AVG(EXTRACT(EPOCH FROM (v.departure_time - v.arrival_time)) / 3600) as turnaround_hours
                        FROM voyages v
                        WHERE v.destination_port_id = %s
                          AND v.arrival_time > NOW() - INTERVAL '%s days'
                          AND v.arrival_time IS NOT NULL
                          AND v.departure_time IS NOT NULL
                          AND v.departure_time > v.arrival_time
                    """, (str(port_id), period_days))
                    dwell_row = cur.fetchone()
                    dwell_median = round(dwell_row[0], 2) if dwell_row and dwell_row[0] else None
                    turnaround = round(dwell_row[1], 2) if dwell_row and dwell_row[1] else None

                    # Current vessels in port (from latest_vessel_positions)
                    # Using simple bounding box for speed
                    deg_offset = radius / 111.0  # rough km to degrees
                    cur.execute("""
                        SELECT COUNT(*) as vessel_count,
                               SUM(CASE WHEN speed < 1.0 THEN 1 ELSE 0 END) as waiting_count
                        FROM latest_vessel_positions
                        WHERE latitude BETWEEN %s AND %s
                          AND longitude BETWEEN %s AND %s
                    """, (lat - deg_offset, lat + deg_offset, lon - deg_offset, lon + deg_offset))
                    pos_row = cur.fetchone()
                    vessel_count = pos_row[0] if pos_row else 0
                    queue_length = pos_row[1] if pos_row and pos_row[1] else 0

                    # Average wait time for vessels currently waiting
                    cur.execute("""
                        SELECT AVG(EXTRACT(EPOCH FROM (NOW() - vp.time)) / 3600) as avg_wait
                        FROM latest_vessel_positions vp
                        WHERE vp.latitude BETWEEN %s AND %s
                          AND vp.longitude BETWEEN %s AND %s
                          AND vp.speed < 1.0
                    """, (lat - deg_offset, lat + deg_offset, lon - deg_offset, lon + deg_offset))
                    wait_row = cur.fetchone()
                    avg_wait = round(wait_row[0], 2) if wait_row and wait_row[0] else None

                    # Upsert analytics
                    period_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                    cur.execute("""
                        INSERT INTO port_analytics
                            (port_id, period_start, period_end, dwell_time_median_hours,
                             turnaround_hours, queue_length, throughput_vessels,
                             vessel_count, avg_wait_hours, calculated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (port_id, period_start) DO UPDATE SET
                            period_end = EXCLUDED.period_end,
                            dwell_time_median_hours = EXCLUDED.dwell_time_median_hours,
                            turnaround_hours = EXCLUDED.turnaround_hours,
                            queue_length = EXCLUDED.queue_length,
                            throughput_vessels = EXCLUDED.throughput_vessels,
                            vessel_count = EXCLUDED.vessel_count,
                            avg_wait_hours = EXCLUDED.avg_wait_hours,
                            calculated_at = EXCLUDED.calculated_at
                    """, (
                        str(port_id), period_start, now, dwell_median,
                        turnaround, queue_length, throughput,
                        vessel_count, avg_wait, now,
                    ))

                    ports_processed += 1

                except Exception as e:
                    logger.error("Failed to calculate analytics for port %s: %s", port_id, e)
                    continue

            conn.commit()

        logger.info("Port analytics calculated for %d ports", ports_processed)
        return {"ports_processed": ports_processed}
    finally:
        conn.close()
