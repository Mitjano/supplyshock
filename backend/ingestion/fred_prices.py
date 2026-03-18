"""FRED (Federal Reserve Economic Data) price ingestion.

Fetches daily energy prices and monthly global commodity prices from FRED API.
Called by Celery beat tasks `ingest_fred_daily` (every 6h) and
`ingest_fred_monthly` (every 24h).
"""

import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

from config import settings

logger = logging.getLogger("fred_prices")

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"

# Daily energy series
DAILY_SERIES: dict[str, str] = {
    "DCOILWTICO": "crude_oil",
    "DCOILBRENTEU": "brent",
    "DHHNGSP": "natural_gas",
    "DPROPANEMBTX": "propane",
    "DHOILNYH": "heating_oil",
    "DGASNYH": "gasoline",
}

# Monthly global commodity series
MONTHLY_SERIES: dict[str, str] = {
    "PZINCUSDM": "zinc",
    "PTINUSDM": "tin",
    "PNICKUSDM": "nickel",
    "PLEADUSDM": "lead",
    "PCOPPUSDM": "copper",
    "PALUMUSDM": "aluminium",
    "PIORECRUSDM": "iron_ore",
    "PCOALAUUSDM": "coal",
    "PURANUSDM": "uranium",
    "PWHEAMTUSDM": "wheat",
    "PCOREUSDM": "corn",
    "PRICENPQUSDM": "rice",
    "PSOYBUSDM": "soybeans",
    "PBEABORUSDM": "beef",
    "PPOULTRYUSDM": "poultry",
    "PSUGAISAUSDM": "sugar",
    "PCOFFOTMUSDM": "coffee",
    "PCOTTINDUSDM": "cotton",
    "PRUBBSGPUSDM": "rubber",
}


# ── Issue #86 — Expanded macro indicators ──
MACRO_SERIES: dict[str, dict] = {
    "DTWEXBGS": {"name": "DTWEXBGS", "description": "Trade Weighted US Dollar Index (DXY proxy)", "unit": "index"},
    "DFF": {"name": "DFF", "description": "Federal Funds Effective Rate", "unit": "percent"},
    "DGS10": {"name": "DGS10", "description": "10-Year Treasury Constant Maturity Rate", "unit": "percent"},
    "T10Y2Y": {"name": "T10Y2Y", "description": "10Y-2Y Treasury Yield Spread", "unit": "percent"},
    "USEPUINDXD": {"name": "USEPUINDXD", "description": "Economic Policy Uncertainty Index", "unit": "index"},
    "INDPRO": {"name": "INDPRO", "description": "Industrial Production Index", "unit": "index_2017_100"},
}


def _fetch_fred_series(series_id: str, api_key: str, lookback_days: int) -> list[dict]:
    """Fetch observations for a single FRED series."""
    start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            FRED_API_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start_date,
                "sort_order": "desc",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("FRED %s returned %d", series_id, resp.status_code)
            return []
        data = resp.json()
        return data.get("observations", [])
    except requests.RequestException as e:
        logger.warning("FRED request failed for %s: %s", series_id, e)
        return []


def _insert_observations(conn, series_map: dict[str, str], observations_by_series: dict, source_tag: str) -> dict:
    """Insert FRED observations into commodity_prices."""
    inserted = 0
    skipped = 0

    with conn.cursor() as cur:
        for series_id, commodity in series_map.items():
            for obs in observations_by_series.get(series_id, []):
                value = obs.get("value", ".")
                if value == "." or not value:
                    skipped += 1
                    continue

                try:
                    price = float(value)
                except (ValueError, TypeError):
                    skipped += 1
                    continue

                if price <= 0:
                    skipped += 1
                    continue

                try:
                    ts = datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, KeyError):
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO commodity_prices (time, commodity, benchmark, price, currency, source)
                    VALUES (%s, %s, %s, %s, 'USD', %s)
                    ON CONFLICT (time, commodity, benchmark) DO NOTHING
                    """,
                    (ts, commodity, series_id, price, source_tag),
                )
                inserted += cur.rowcount

        conn.commit()

    return {"inserted": inserted, "skipped": skipped}


def ingest_fred_daily(api_key: str) -> dict:
    """Fetch last 5 days of daily FRED energy series."""
    logger.info("Fetching FRED daily series (%d series)", len(DAILY_SERIES))

    observations_by_series = {}
    for series_id in DAILY_SERIES:
        observations_by_series[series_id] = _fetch_fred_series(series_id, api_key, lookback_days=5)

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        result = _insert_observations(conn, DAILY_SERIES, observations_by_series, "fred_daily")
        logger.info("FRED daily ingest: %d inserted, %d skipped", result["inserted"], result["skipped"])
        return result
    finally:
        conn.close()


def ingest_fred_monthly(api_key: str) -> dict:
    """Fetch last 2 months of monthly FRED commodity series."""
    logger.info("Fetching FRED monthly series (%d series)", len(MONTHLY_SERIES))

    observations_by_series = {}
    for series_id in MONTHLY_SERIES:
        observations_by_series[series_id] = _fetch_fred_series(series_id, api_key, lookback_days=62)

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        result = _insert_observations(conn, MONTHLY_SERIES, observations_by_series, "fred_monthly")
        logger.info("FRED monthly ingest: %d inserted, %d skipped", result["inserted"], result["skipped"])
        return result
    finally:
        conn.close()


def ingest_fred_macro(api_key: str) -> dict:
    """Fetch expanded macro indicators from FRED (Issue #86).

    Stores in macro_indicators table (not commodity_prices).
    Series: DXY proxy, Fed Funds, 10Y, yield curve, EPU, INDPRO.
    """
    logger.info("Fetching FRED macro series (%d series)", len(MACRO_SERIES))

    observations_by_series = {}
    for series_id in MACRO_SERIES:
        observations_by_series[series_id] = _fetch_fred_series(series_id, api_key, lookback_days=10)

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    inserted = 0
    skipped = 0

    try:
        with conn.cursor() as cur:
            # Ensure macro_indicators table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS macro_indicators (
                    id BIGSERIAL PRIMARY KEY,
                    indicator TEXT NOT NULL,
                    time TIMESTAMPTZ NOT NULL,
                    value DOUBLE PRECISION NOT NULL,
                    unit TEXT,
                    source TEXT NOT NULL,
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (indicator, time, source)
                )
            """)

            for series_id, config in MACRO_SERIES.items():
                for obs in observations_by_series.get(series_id, []):
                    value = obs.get("value", ".")
                    if value == "." or not value:
                        skipped += 1
                        continue
                    try:
                        val = float(value)
                    except (ValueError, TypeError):
                        skipped += 1
                        continue

                    try:
                        ts = datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except (ValueError, KeyError):
                        skipped += 1
                        continue

                    cur.execute(
                        """
                        INSERT INTO macro_indicators (indicator, time, value, unit, source)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (indicator, time, source) DO UPDATE SET
                            value = EXCLUDED.value,
                            ingested_at = NOW()
                        """,
                        (series_id, ts, val, config["unit"], "fred"),
                    )
                    inserted += cur.rowcount

        conn.commit()
        logger.info("FRED macro ingest: %d inserted, %d skipped", inserted, skipped)
    finally:
        conn.close()

    return {"inserted": inserted, "skipped": skipped}
