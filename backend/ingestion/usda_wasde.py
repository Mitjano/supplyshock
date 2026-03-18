"""USDA WASDE (World Agricultural Supply and Demand Estimates) ingestion.

Fetches supply/demand balance data for corn, wheat, soybeans from USDA FAS API.
Called by Celery beat task `import_usda_wasde` monthly on the 12th.
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger("usda_wasde")

USDA_FAS_BASE = "https://apps.fas.usda.gov/OpenData/api/psd"

# USDA commodity codes and metrics we track
WASDE_COMMODITIES = {
    "0440000": {  # Corn
        "commodity": "corn",
        "metrics": {
            "Production": "production",
            "Domestic Consumption": "consumption",
            "Ending Stocks": "ending_stocks",
            "Exports": "exports",
        },
    },
    "0410000": {  # Wheat
        "commodity": "wheat",
        "metrics": {
            "Production": "production",
            "Domestic Consumption": "consumption",
            "Ending Stocks": "ending_stocks",
            "Exports": "exports",
        },
    },
    "2222000": {  # Soybeans
        "commodity": "soybeans",
        "metrics": {
            "Production": "production",
            "Domestic Consumption": "consumption",
            "Ending Stocks": "ending_stocks",
            "Exports": "exports",
        },
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
                source TEXT NOT NULL DEFAULT 'usda_wasde',
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (commodity, metric, period, source)
            )
        """)
    conn.commit()


def import_usda_wasde() -> dict:
    """Fetch WASDE data from USDA and store in supply_demand_balance table."""
    records = []
    now = datetime.now(timezone.utc)
    current_year = now.year

    for commodity_code, config in WASDE_COMMODITIES.items():
        try:
            # Fetch world-level PSD data for the commodity
            url = f"{USDA_FAS_BASE}/commodity/{commodity_code}"
            resp = httpx.get(
                url,
                params={
                    "marketYear": current_year,
                    "countryCode": "XX",  # World aggregate
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                data = [data] if data else []

            for item in data:
                attribute_desc = item.get("attributeDescription", "")
                market_year = item.get("marketYear", current_year)
                value = item.get("value")

                if attribute_desc in config["metrics"] and value is not None:
                    try:
                        val = float(value)
                    except (ValueError, TypeError):
                        continue

                    unit = item.get("unitDescription", "1000 MT")
                    period = f"{market_year}"

                    records.append({
                        "commodity": config["commodity"],
                        "metric": config["metrics"][attribute_desc],
                        "value": val,
                        "unit": unit,
                        "period": period,
                        "source": "usda_wasde",
                    })

        except Exception as e:
            logger.error("WASDE fetch failed for %s (%s): %s", config["commodity"], commodity_code, e)

    if not records:
        logger.info("No WASDE records fetched")
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
        logger.info("WASDE import: %d records upserted", len(records))
        return {"inserted": len(records)}
    finally:
        conn.close()
