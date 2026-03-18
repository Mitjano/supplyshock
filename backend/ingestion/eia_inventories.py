"""EIA inventory data ingestion.

Fetches weekly petroleum inventory data (crude stocks, gasoline, distillate,
refinery utilization, Cushing stocks) from EIA API v2.
Runs weekly via Celery Beat (Wednesday 17:00 UTC — after EIA weekly release).

Issue #65
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

EIA_BASE_URL = "https://api.eia.gov/v2"

# EIA API v2 inventory series
EIA_INVENTORY_SERIES: dict[str, dict] = {
    "crude_stocks": {
        "route": "petroleum/stoc/wstk",
        "facet_series": "WCESTUS1",
        "description": "US Commercial Crude Oil Stocks (excl. SPR)",
        "unit": "thousand_barrels",
    },
    "gasoline_stocks": {
        "route": "petroleum/stoc/wstk",
        "facet_series": "WGTSTUS1",
        "description": "US Total Gasoline Stocks",
        "unit": "thousand_barrels",
    },
    "distillate_stocks": {
        "route": "petroleum/stoc/wstk",
        "facet_series": "WDISTUS1",
        "description": "US Distillate Fuel Oil Stocks",
        "unit": "thousand_barrels",
    },
    "refinery_utilization": {
        "route": "petroleum/pnp/wiup",
        "facet_series": "WPULEUS3",
        "description": "US Percent Utilization of Refinery Operable Capacity",
        "unit": "percent",
    },
    "cushing_stocks": {
        "route": "petroleum/stoc/wstk",
        "facet_series": "WCESTP21",
        "description": "Cushing, OK Crude Oil Stocks",
        "unit": "thousand_barrels",
    },
}


def fetch_eia_inventories() -> list[dict]:
    """Fetch latest inventory data from EIA API v2."""
    api_key = settings.EIA_API_KEY
    if not api_key:
        logger.error("EIA_API_KEY not set — skipping inventory ingestion")
        return []

    records: list[dict] = []
    for series_key, config in EIA_INVENTORY_SERIES.items():
        try:
            url = f"{EIA_BASE_URL}/{config['route']}/data/"
            resp = httpx.get(
                url,
                params={
                    "api_key": api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[series][]": config["facet_series"],
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "length": 52,  # last year of weekly data
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            series_data = data.get("response", {}).get("data", [])
            for entry in series_data:
                value = entry.get("value")
                if value is None:
                    continue

                period = entry.get("period", "")
                try:
                    report_time = datetime.strptime(period, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError):
                    continue

                records.append({
                    "series": series_key,
                    "time": report_time.isoformat(),
                    "value": float(value),
                    "unit": config["unit"],
                })

            logger.info("Fetched %d entries for %s", len(series_data), series_key)
        except Exception as e:
            logger.error("EIA inventory fetch failed for %s: %s", series_key, e)

    return records


def ingest_eia_inventories() -> int:
    """Fetch and store EIA inventory data. Returns number of rows upserted."""
    records = fetch_eia_inventories()
    if not records:
        logger.info("No EIA inventory records to ingest")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS eia_inventories (
                    id BIGSERIAL PRIMARY KEY,
                    series TEXT NOT NULL,
                    time TIMESTAMPTZ NOT NULL,
                    value DOUBLE PRECISION NOT NULL,
                    unit TEXT NOT NULL,
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (series, time)
                )
            """)
            values = [
                (r["series"], r["time"], r["value"], r["unit"])
                for r in records
            ]
            execute_values(
                cur,
                """
                INSERT INTO eia_inventories (series, time, value, unit)
                VALUES %s
                ON CONFLICT (series, time) DO UPDATE SET
                    value = EXCLUDED.value,
                    ingested_at = NOW()
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d EIA inventory records", len(records))
    finally:
        conn.close()

    return len(records)
