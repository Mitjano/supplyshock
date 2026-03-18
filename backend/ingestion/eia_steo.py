"""EIA Short-Term Energy Outlook (STEO) ingestion.

Fetches world oil production, consumption, and OECD stock data from EIA API v2.
Called by Celery beat task `import_eia_steo` monthly on the 1st.
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger("eia_steo")

EIA_BASE_URL = "https://api.eia.gov/v2"

# STEO series we want to track
STEO_SERIES = {
    "world_production": {
        "route": "steo",
        "facet_series": "PAPR_WORLD",
        "commodity": "crude_oil",
        "metric": "production",
        "unit": "mb/d",
    },
    "world_consumption": {
        "route": "steo",
        "facet_series": "PATC_WORLD",
        "commodity": "crude_oil",
        "metric": "consumption",
        "unit": "mb/d",
    },
    "oecd_stocks": {
        "route": "steo",
        "facet_series": "T3&STEO.PASC_OECD.M",
        "commodity": "crude_oil",
        "metric": "ending_stocks",
        "unit": "million_barrels",
    },
    "us_production": {
        "route": "steo",
        "facet_series": "PAPR_US",
        "commodity": "crude_oil",
        "metric": "production_us",
        "unit": "mb/d",
    },
    "ng_production": {
        "route": "steo",
        "facet_series": "NGPL_US",
        "commodity": "natural_gas",
        "metric": "production",
        "unit": "bcf/d",
    },
    "ng_consumption": {
        "route": "steo",
        "facet_series": "NGTC_US",
        "commodity": "natural_gas",
        "metric": "consumption",
        "unit": "bcf/d",
    },
}


def _ensure_table(conn):
    """Create supply_demand_balance table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS supply_demand_balance (
                id BIGSERIAL PRIMARY KEY,
                commodity TEXT NOT NULL,
                metric TEXT NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                unit TEXT,
                period TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'eia_steo',
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (commodity, metric, period, source)
            )
        """)
    conn.commit()


def import_eia_steo() -> dict:
    """Fetch STEO data from EIA and store in supply_demand_balance table."""
    api_key = settings.EIA_API_KEY
    if not api_key:
        logger.error("EIA_API_KEY not set — skipping STEO import")
        return {"error": "EIA_API_KEY not set"}

    records = []

    for key, config in STEO_SERIES.items():
        try:
            url = f"{EIA_BASE_URL}/{config['route']}/data/"
            resp = httpx.get(
                url,
                params={
                    "api_key": api_key,
                    "frequency": "monthly",
                    "data[0]": "value",
                    "facets[seriesId][]": config["facet_series"],
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "length": 24,  # last 24 months
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            series_data = data.get("response", {}).get("data", [])
            for item in series_data:
                value = item.get("value")
                if value is None:
                    continue
                try:
                    val = float(value)
                except (ValueError, TypeError):
                    continue

                period = item.get("period", "")
                records.append({
                    "commodity": config["commodity"],
                    "metric": config["metric"],
                    "value": val,
                    "unit": config["unit"],
                    "period": period,
                    "source": "eia_steo",
                })

        except Exception as e:
            logger.error("STEO fetch failed for %s: %s", key, e)

    if not records:
        logger.info("No STEO records fetched")
        return {"inserted": 0}

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            values = [
                (r["commodity"], r["metric"], r["value"], r["unit"], r["period"], r["source"])
                for r in records
            ]
            execute_values(
                cur,
                """
                INSERT INTO supply_demand_balance (commodity, metric, value, unit, period, source)
                VALUES %s
                ON CONFLICT (commodity, metric, period, source) DO UPDATE
                    SET value = EXCLUDED.value, fetched_at = NOW()
                """,
                values,
            )
        conn.commit()
        logger.info("STEO import: %d records upserted", len(records))
        return {"inserted": len(records)}
    finally:
        conn.close()
