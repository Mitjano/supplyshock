"""Baker Hughes rig count ingestion (Issue #81).

Fetches US oil/gas rig counts by basin via EIA API v2.
Series: RIGS.RES02-0000.W

Celery Beat: Friday 19:00 UTC (Baker Hughes releases Fridays at 1 PM ET).
"""

import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

from config import settings

logger = logging.getLogger("baker_hughes")

EIA_API_BASE = "https://api.eia.gov/v2"

# EIA Rig Count series IDs
RIG_SERIES = {
    # US total
    "RIGS.RES02-0000.W": {"type": "total", "region": "US", "name": "US Total Rigs"},
    # Oil rigs
    "RIGS.RES02-OIL.W": {"type": "oil", "region": "US", "name": "US Oil Rigs"},
    # Gas rigs
    "RIGS.RES02-GAS.W": {"type": "gas", "region": "US", "name": "US Gas Rigs"},
    # Miscellaneous
    "RIGS.RES02-MSC.W": {"type": "misc", "region": "US", "name": "US Misc Rigs"},
}

# Major basins (if available via EIA facets)
BASINS = {
    "permian": "Permian Basin",
    "eagle_ford": "Eagle Ford",
    "bakken": "Bakken",
    "niobrara": "DJ-Niobrara",
    "haynesville": "Haynesville",
    "marcellus": "Marcellus",
    "utica": "Utica",
}


def _ensure_table(conn):
    """Create rig_counts table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rig_counts (
                id BIGSERIAL PRIMARY KEY,
                report_date DATE NOT NULL,
                region TEXT NOT NULL,
                rig_type TEXT NOT NULL,
                count INTEGER NOT NULL,
                basin TEXT,
                source TEXT NOT NULL DEFAULT 'eia',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (report_date, region, rig_type, COALESCE(basin, ''))
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rig_counts_lookup
            ON rig_counts (region, rig_type, report_date DESC)
        """)
    conn.commit()


def _fetch_eia_rigs(series_id: str, api_key: str, weeks: int = 104) -> list[dict]:
    """Fetch rig count data from EIA API v2."""
    try:
        # EIA v2 API for drilling data
        url = f"{EIA_API_BASE}/drilling-info/data/"
        params = {
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": weeks,
        }
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            records = data.get("response", {}).get("data", [])
            return records
        else:
            logger.warning("EIA API returned %d for rigs", resp.status_code)
    except Exception as e:
        logger.error("Failed to fetch EIA rig data: %s", e)

    # Fallback: try series-based endpoint
    try:
        url = f"{EIA_API_BASE}/seriesid/{series_id}"
        params = {
            "api_key": api_key,
            "num": weeks,
        }
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", {}).get("data", [])
    except Exception as e:
        logger.error("EIA series fallback failed: %s", e)

    return []


def ingest_baker_hughes():
    """Ingest Baker Hughes rig count data via EIA API."""
    api_key = getattr(settings, "EIA_API_KEY", None)
    if not api_key:
        logger.error("EIA_API_KEY not configured")
        return {"error": "EIA_API_KEY not configured"}

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        total = 0

        for series_id, meta in RIG_SERIES.items():
            records = _fetch_eia_rigs(series_id, api_key)
            if not records:
                continue

            with conn.cursor() as cur:
                for rec in records:
                    period = rec.get("period", "")
                    value = rec.get("value")
                    if not period or value is None:
                        continue

                    try:
                        count = int(float(value))
                    except (ValueError, TypeError):
                        continue

                    basin = rec.get("duoarea", rec.get("basin"))

                    try:
                        cur.execute("""
                            INSERT INTO rig_counts
                                (report_date, region, rig_type, count, basin, source)
                            VALUES (%s, %s, %s, %s, %s, 'eia')
                            ON CONFLICT (report_date, region, rig_type, COALESCE(basin, ''))
                            DO UPDATE SET count = EXCLUDED.count
                        """, (
                            period,
                            meta["region"],
                            meta["type"],
                            count,
                            basin,
                        ))
                        total += 1
                    except Exception as e:
                        logger.warning("Failed to upsert rig count %s/%s: %s", meta["type"], period, e)
                        conn.rollback()
                        continue

            conn.commit()
            logger.info("Ingested %d rig count records for %s", len(records), meta["name"])

        logger.info("Baker Hughes rig count ingestion complete: %d records", total)
        return {"records_ingested": total}
    finally:
        conn.close()
