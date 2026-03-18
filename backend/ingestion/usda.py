"""USDA crop data ingestion.

Fetches crop progress, condition, and export sales from:
- USDA NASS QuickStats API (crop progress & condition)
- USDA FAS (weekly export sales)

Stores in crop_data table (auto-created).
Runs Mon & Thu via Celery Beat.

Issue #84
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

NASS_API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
FAS_API_URL = "https://apps.fas.usda.gov/OpenData/api/esr/exports"

# Key commodities
CROP_COMMODITIES = ["CORN", "WHEAT", "SOYBEANS", "COTTON", "SORGHUM"]


def _ensure_crop_table(conn) -> None:
    """Create crop_data table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crop_data (
                id BIGSERIAL PRIMARY KEY,
                commodity TEXT NOT NULL,
                data_type TEXT NOT NULL,
                week_ending TEXT,
                year INTEGER,
                value DOUBLE PRECISION,
                unit TEXT,
                state TEXT,
                source TEXT NOT NULL,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (commodity, data_type, week_ending, state, source)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_crop_data_commodity
            ON crop_data (commodity, data_type)
        """)
    conn.commit()


def fetch_crop_progress(commodity: str = "CORN") -> list[dict]:
    """Fetch crop progress data from USDA NASS QuickStats."""
    api_key = settings.USDA_NASS_API_KEY if hasattr(settings, "USDA_NASS_API_KEY") else getattr(settings, "USDA_API_KEY", "")
    if not api_key:
        logger.error("USDA_NASS_API_KEY not set — skipping crop progress")
        return []

    records: list[dict] = []
    current_year = datetime.now(timezone.utc).year

    try:
        resp = httpx.get(
            NASS_API_URL,
            params={
                "key": api_key,
                "commodity_desc": commodity.upper(),
                "statisticcat_desc": "PROGRESS",
                "unit_desc": "PCT PLANTED",
                "year": current_year,
                "agg_level_desc": "NATIONAL",
                "format": "JSON",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        for entry in data:
            value = entry.get("Value")
            if value is None or value == "" or value == "(D)":
                continue
            try:
                val = float(str(value).replace(",", ""))
            except (ValueError, TypeError):
                continue

            records.append({
                "commodity": commodity.lower(),
                "data_type": "progress_planted",
                "week_ending": entry.get("week_ending", ""),
                "year": int(entry.get("year", current_year)),
                "value": val,
                "unit": "percent",
                "state": entry.get("state_name", "US TOTAL"),
                "source": "usda_nass",
            })

        # Also fetch condition data
        resp2 = httpx.get(
            NASS_API_URL,
            params={
                "key": api_key,
                "commodity_desc": commodity.upper(),
                "statisticcat_desc": "CONDITION",
                "unit_desc": "PCT GOOD",
                "year": current_year,
                "agg_level_desc": "NATIONAL",
                "format": "JSON",
            },
            timeout=30,
        )
        resp2.raise_for_status()
        cond_data = resp2.json().get("data", [])

        for entry in cond_data:
            value = entry.get("Value")
            if value is None or value == "" or value == "(D)":
                continue
            try:
                val = float(str(value).replace(",", ""))
            except (ValueError, TypeError):
                continue

            records.append({
                "commodity": commodity.lower(),
                "data_type": "condition_good",
                "week_ending": entry.get("week_ending", ""),
                "year": int(entry.get("year", current_year)),
                "value": val,
                "unit": "percent",
                "state": entry.get("state_name", "US TOTAL"),
                "source": "usda_nass",
            })

        logger.info("Fetched %d NASS records for %s", len(records), commodity)

    except Exception as e:
        logger.error("USDA NASS fetch failed for %s: %s", commodity, e)

    return records


def fetch_export_sales(commodity: str = "WHEAT") -> list[dict]:
    """Fetch weekly export sales from USDA FAS."""
    records: list[dict] = []

    # Map commodity names to FAS commodity codes
    fas_codes = {
        "wheat": "0401100",
        "corn": "0440000",
        "soybeans": "0801100",
        "cotton": "3001100",
        "sorghum": "0459100",
    }

    code = fas_codes.get(commodity.lower())
    if not code:
        logger.warning("No FAS code for commodity: %s", commodity)
        return []

    try:
        resp = httpx.get(
            f"{FAS_API_URL}/{code}",
            timeout=30,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        for entry in data if isinstance(data, list) else []:
            weekly_exports = entry.get("weeklyExports")
            if weekly_exports is None:
                continue

            records.append({
                "commodity": commodity.lower(),
                "data_type": "export_sales",
                "week_ending": entry.get("weekEndingDate", ""),
                "year": int(entry.get("marketYear", datetime.now(timezone.utc).year)),
                "value": float(weekly_exports),
                "unit": "metric_tons",
                "state": entry.get("countryDescription", "TOTAL"),
                "source": "usda_fas",
            })

        logger.info("Fetched %d FAS export records for %s", len(records), commodity)

    except Exception as e:
        logger.error("USDA FAS fetch failed for %s: %s", commodity, e)

    return records


def ingest_usda_crops() -> int:
    """Fetch and store USDA crop progress, condition, and export sales."""
    all_records: list[dict] = []

    for commodity in CROP_COMMODITIES:
        all_records.extend(fetch_crop_progress(commodity))
        all_records.extend(fetch_export_sales(commodity))

    if not all_records:
        logger.info("No USDA crop records to ingest")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_crop_table(conn)
        with conn.cursor() as cur:
            values = [
                (r["commodity"], r["data_type"], r["week_ending"], r["year"],
                 r["value"], r["unit"], r["state"], r["source"])
                for r in all_records
            ]
            execute_values(
                cur,
                """
                INSERT INTO crop_data
                    (commodity, data_type, week_ending, year, value, unit, state, source)
                VALUES %s
                ON CONFLICT (commodity, data_type, week_ending, state, source)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    year = EXCLUDED.year,
                    ingested_at = NOW()
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d USDA crop records", len(all_records))
    finally:
        conn.close()

    return len(all_records)
