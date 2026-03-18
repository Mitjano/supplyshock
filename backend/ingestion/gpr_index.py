"""Geopolitical Risk (GPR) Index ingestion (Issue #80).

Downloads monthly GPR index CSV from Matteo Iacoviello's website
(Federal Reserve Board) and stores values in macro_indicators table.

Celery Beat: weekly (Monday 7:00 UTC).
"""

import logging
from datetime import datetime, timezone
from io import StringIO

import psycopg2
import requests

from config import settings

logger = logging.getLogger("gpr_index")

# GPR Index CSV from Matteo Iacoviello's site
GPR_CSV_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.csv"
GPR_MONTHLY_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"

# Country-specific GPR series available
GPR_SERIES = {
    "GPRD": "global",        # Global Daily GPR
    "GPRD_ACT": "global",    # GPR Acts (actual threats)
    "GPRD_THR": "global",    # GPR Threats
}

# Monthly GPR for specific countries
GPR_COUNTRY_SERIES = {
    "GPR": "global",
    "GPR_USA": "US",
    "GPR_CHN": "CN",
    "GPR_RUS": "RU",
    "GPR_SAU": "SA",
    "GPR_IRN": "IR",
    "GPR_ISR": "IL",
    "GPR_UKR": "UA",
    "GPR_GBR": "GB",
}


def _ensure_table(conn):
    """Ensure macro_indicators table exists (shared with dbnomics)."""
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


def _fetch_gpr_csv() -> list[dict]:
    """Fetch and parse GPR index CSV data."""
    results = []

    # Try daily recent data first
    try:
        resp = requests.get(GPR_CSV_URL, timeout=30)
        if resp.status_code == 200:
            content = resp.text
            lines = content.strip().split("\n")
            if len(lines) < 2:
                logger.warning("GPR CSV has no data rows")
                return results

            headers = [h.strip().strip('"') for h in lines[0].split(",")]

            for line in lines[1:]:
                if not line.strip():
                    continue
                values = [v.strip().strip('"') for v in line.split(",")]
                if len(values) < 2:
                    continue

                row = dict(zip(headers, values))
                date_str = row.get("date", row.get("Date", ""))
                if not date_str:
                    continue

                # Parse date (various formats)
                period = None
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
                    try:
                        period = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue

                if period is None:
                    continue

                # Extract GPR values
                for col, country in GPR_SERIES.items():
                    val_str = row.get(col, "")
                    if val_str and val_str not in ("", "NA", "."):
                        try:
                            results.append({
                                "indicator": "gpr",
                                "country": country,
                                "period": period,
                                "value": float(val_str),
                            })
                        except ValueError:
                            continue

                # Country-specific GPR
                for col, country in GPR_COUNTRY_SERIES.items():
                    val_str = row.get(col, "")
                    if val_str and val_str not in ("", "NA", "."):
                        try:
                            results.append({
                                "indicator": "gpr",
                                "country": country,
                                "period": period,
                                "value": float(val_str),
                            })
                        except ValueError:
                            continue

            logger.info("Parsed %d GPR records from CSV", len(results))
        else:
            logger.warning("GPR CSV download returned %d", resp.status_code)
    except Exception as e:
        logger.error("Failed to fetch GPR CSV: %s", e)

    return results


def ingest_gpr_index():
    """Ingest GPR index data into macro_indicators table."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)

        records = _fetch_gpr_csv()
        if not records:
            logger.warning("No GPR data fetched")
            return {"records_ingested": 0}

        total = 0
        with conn.cursor() as cur:
            for rec in records:
                try:
                    cur.execute("""
                        INSERT INTO macro_indicators
                            (indicator, country, period, value, source)
                        VALUES (%s, %s, %s, %s, 'gpr')
                        ON CONFLICT (indicator, country, period, source)
                        DO UPDATE SET value = EXCLUDED.value
                    """, (
                        rec["indicator"],
                        rec["country"],
                        rec["period"],
                        rec["value"],
                    ))
                    total += 1
                except Exception as e:
                    logger.warning("Failed to upsert GPR %s/%s: %s", rec["country"], rec["period"], e)
                    conn.rollback()
                    continue

        conn.commit()
        logger.info("GPR index ingestion complete: %d records", total)
        return {"records_ingested": total}
    finally:
        conn.close()
