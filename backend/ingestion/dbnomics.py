"""DBnomics macro data ingestion (Issue #77).

Fetches macro indicators from DBnomics API v22 (free, no key required):
- IMF IFS industrial production indices
- OECD PMI (Purchasing Managers' Index)
- ECB FX rates

Celery Beat: every 12 hours.
"""

import logging
from datetime import datetime, timezone

import psycopg2
import requests

from config import settings

logger = logging.getLogger("dbnomics")

DBNOMICS_BASE = "https://db.nomics.world/api/v22"

# Series definitions: (provider/dataset/series_code, indicator_name, country)
SERIES_MAP = [
    # IMF IFS — Industrial Production Index
    ("IMF/IFS/M.US.AIP_IX", "industrial_production", "US"),
    ("IMF/IFS/M.CN.AIP_IX", "industrial_production", "CN"),
    ("IMF/IFS/M.DE.AIP_IX", "industrial_production", "DE"),
    ("IMF/IFS/M.JP.AIP_IX", "industrial_production", "JP"),
    ("IMF/IFS/M.GB.AIP_IX", "industrial_production", "GB"),
    ("IMF/IFS/M.IN.AIP_IX", "industrial_production", "IN"),
    ("IMF/IFS/M.KR.AIP_IX", "industrial_production", "KR"),
    # OECD PMI — Composite Leading Indicators
    ("OECD/MEI_CLI/LOLITOAA.USA.M", "pmi", "US"),
    ("OECD/MEI_CLI/LOLITOAA.CHN.M", "pmi", "CN"),
    ("OECD/MEI_CLI/LOLITOAA.EA19.M", "pmi", "EU"),
    ("OECD/MEI_CLI/LOLITOAA.DEU.M", "pmi", "DE"),
    ("OECD/MEI_CLI/LOLITOAA.JPN.M", "pmi", "JP"),
    ("OECD/MEI_CLI/LOLITOAA.GBR.M", "pmi", "GB"),
    ("OECD/MEI_CLI/LOLITOAA.IND.M", "pmi", "IN"),
    # ECB FX rates
    ("ECB/EXR/M.USD.EUR.SP00.A", "fx_rate", "USD_EUR"),
    ("ECB/EXR/M.CNY.EUR.SP00.A", "fx_rate", "CNY_EUR"),
    ("ECB/EXR/M.JPY.EUR.SP00.A", "fx_rate", "JPY_EUR"),
    ("ECB/EXR/M.GBP.EUR.SP00.A", "fx_rate", "GBP_EUR"),
]


def _ensure_table(conn):
    """Create macro_indicators table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS macro_indicators (
                id BIGSERIAL PRIMARY KEY,
                indicator TEXT NOT NULL,
                country TEXT NOT NULL,
                period DATE NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                source TEXT NOT NULL DEFAULT 'dbnomics',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (indicator, country, period, source)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_macro_indicators_lookup
            ON macro_indicators (indicator, country, period DESC)
        """)
    conn.commit()


def _fetch_series(series_id: str, limit: int = 120) -> list[dict]:
    """Fetch a single series from DBnomics."""
    try:
        url = f"{DBNOMICS_BASE}/series/{series_id}"
        params = {"observations": 1, "limit": 1}
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            logger.warning("DBnomics returned %d for %s", resp.status_code, series_id)
            return []

        data = resp.json()
        series_list = data.get("series", {}).get("docs", [])
        if not series_list:
            return []

        series_data = series_list[0]
        periods = series_data.get("period", [])
        values = series_data.get("value", [])

        results = []
        for period, value in zip(periods[-limit:], values[-limit:]):
            if value is None or value == "NA":
                continue
            try:
                results.append({
                    "period": period,
                    "value": float(value),
                })
            except (ValueError, TypeError):
                continue

        return results
    except Exception as e:
        logger.error("Failed to fetch DBnomics series %s: %s", series_id, e)
        return []


def ingest_dbnomics():
    """Ingest macro indicators from DBnomics."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        total = 0

        for series_id, indicator, country in SERIES_MAP:
            records = _fetch_series(series_id)
            if not records:
                continue

            with conn.cursor() as cur:
                for rec in records:
                    try:
                        cur.execute("""
                            INSERT INTO macro_indicators
                                (indicator, country, period, value, source)
                            VALUES (%s, %s, %s, %s, 'dbnomics')
                            ON CONFLICT (indicator, country, period, source)
                            DO UPDATE SET value = EXCLUDED.value
                        """, (
                            indicator,
                            country,
                            rec["period"],
                            rec["value"],
                        ))
                        total += 1
                    except Exception as e:
                        logger.warning("Failed to upsert %s/%s/%s: %s", indicator, country, rec["period"], e)
                        conn.rollback()
                        continue

            conn.commit()
            logger.info("Ingested %d records for %s/%s", len(records), indicator, country)

        logger.info("DBnomics ingestion complete: %d total records", total)
        return {"records_ingested": total}
    finally:
        conn.close()
