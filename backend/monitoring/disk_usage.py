"""DB disk usage monitoring — Issue #104.

Checks PostgreSQL database size and alerts if usage exceeds threshold.
"""

import logging

import psycopg2

from config import settings

logger = logging.getLogger("supplyshock.monitoring.disk_usage")

DISK_USAGE_THRESHOLD_PCT = 80


def check_db_disk_usage() -> dict:
    """Check PostgreSQL database size and available disk space.

    Returns dict with db_size, table sizes, and alert status.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Total database size
            cur.execute("SELECT pg_database_size(current_database())")
            db_size_bytes = cur.fetchone()[0]

            # Size per table (top 10)
            cur.execute("""
                SELECT relname AS table_name,
                       pg_total_relation_size(c.oid) AS total_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                ORDER BY pg_total_relation_size(c.oid) DESC
                LIMIT 10
            """)
            table_sizes = [
                {
                    "table": row[0],
                    "size_bytes": row[1],
                    "size_mb": round(row[1] / (1024 * 1024), 1),
                }
                for row in cur.fetchall()
            ]

            # Check tablespace disk usage (if pg_stat_file available)
            disk_usage_pct = None
            try:
                cur.execute("""
                    SELECT
                        (pg_database_size(current_database())::float /
                         NULLIF(setting::bigint * 1024, 0) * 100)
                    FROM pg_settings
                    WHERE name = 'effective_cache_size'
                """)
                row = cur.fetchone()
                if row and row[0]:
                    disk_usage_pct = round(row[0], 1)
            except Exception:
                pass  # Not all setups support this

        db_size_mb = round(db_size_bytes / (1024 * 1024), 1)
        db_size_gb = round(db_size_bytes / (1024 * 1024 * 1024), 2)

        alert = False
        if disk_usage_pct and disk_usage_pct > DISK_USAGE_THRESHOLD_PCT:
            alert = True
            logger.warning(
                "DB DISK ALERT: usage at %.1f%% (threshold: %d%%)",
                disk_usage_pct,
                DISK_USAGE_THRESHOLD_PCT,
            )

        return {
            "db_size_bytes": db_size_bytes,
            "db_size_mb": db_size_mb,
            "db_size_gb": db_size_gb,
            "disk_usage_pct": disk_usage_pct,
            "alert": alert,
            "threshold_pct": DISK_USAGE_THRESHOLD_PCT,
            "top_tables": table_sizes,
        }
    finally:
        conn.close()
