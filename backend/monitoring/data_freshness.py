"""Data freshness monitoring — Issue #103.

Checks MAX(created_at) / MAX(time) per data table and alerts if data is stale.
Can be called as a Celery task or via the admin health endpoint.
"""

import logging
from datetime import datetime, timedelta, timezone

import psycopg2

from config import settings

logger = logging.getLogger("supplyshock.monitoring.data_freshness")

# Tables to monitor: (table_name, timestamp_column, max_age_hours)
MONITORED_TABLES = [
    ("vessel_positions", "time", 1),
    ("commodity_prices", "time", 12),
    ("eia_inventories", "time", 168),        # weekly data — 7 days
    ("supply_demand_balance", "fetched_at", 744),  # monthly — 31 days
    ("alert_events", "time", 24),
    ("chokepoint_status", "time", 1),
]


def check_data_freshness() -> list[dict]:
    """Check each monitored table for stale data.

    Returns a list of dicts with table name, last timestamp, and whether it's stale.
    """
    results: list[dict] = []
    now = datetime.now(timezone.utc)

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            for table, ts_col, max_age_hours in MONITORED_TABLES:
                try:
                    cur.execute(
                        f"SELECT MAX({ts_col}) FROM {table}"  # table names are hardcoded, not user input
                    )
                    row = cur.fetchone()
                    last_ts = row[0] if row else None

                    if last_ts is None:
                        stale = True
                        age_hours = None
                    else:
                        if last_ts.tzinfo is None:
                            last_ts = last_ts.replace(tzinfo=timezone.utc)
                        age = now - last_ts
                        age_hours = age.total_seconds() / 3600
                        stale = age_hours > max_age_hours

                    result = {
                        "table": table,
                        "last_timestamp": last_ts.isoformat() if last_ts else None,
                        "age_hours": round(age_hours, 1) if age_hours is not None else None,
                        "max_age_hours": max_age_hours,
                        "stale": stale,
                    }
                    results.append(result)

                    if stale:
                        logger.warning(
                            "STALE DATA: %s — last update %s (max allowed: %dh)",
                            table,
                            f"{age_hours:.1f}h ago" if age_hours else "NEVER",
                            max_age_hours,
                        )
                except Exception as e:
                    logger.error("Failed to check freshness for %s: %s", table, e)
                    results.append({
                        "table": table,
                        "last_timestamp": None,
                        "age_hours": None,
                        "max_age_hours": max_age_hours,
                        "stale": True,
                        "error": str(e),
                    })
    finally:
        conn.close()

    return results
