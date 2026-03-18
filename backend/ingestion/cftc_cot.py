"""CFTC Commitments of Traders (COT) report ingestion.

Downloads weekly COT data from CFTC and parses commercial/non-commercial
positions for key commodities.  Runs weekly via Celery Beat (Friday 22:00 UTC).

Issue #64
"""

import csv
import io
import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

CFTC_URL = "https://www.cftc.gov/dea/newcot/deacom.txt"

# Map CFTC Market_and_Exchange_Names substrings → our commodity_type
CFTC_MARKET_MAP: dict[str, str] = {
    "CRUDE OIL, LIGHT SWEET": "crude_oil",
    "NATURAL GAS": "natural_gas",
    "GOLD": "gold",
    "SILVER": "silver",
    "COPPER": "copper",
    "WHEAT": "wheat",
    "CORN": "corn",
    "SOYBEANS": "soybeans",
}

# Column indices in the deacom.txt CSV (Disaggregated Futures-Only)
# Ref: https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm
COL_MARKET_NAME = 0
COL_REPORT_DATE = 2       # As_of_Date_In_Form_YYMMDD  (actually YYYY-MM-DD in newer files)
COL_OPEN_INTEREST = 7
COL_NONCOMM_LONG = 8
COL_NONCOMM_SHORT = 9
COL_COMM_LONG = 11
COL_COMM_SHORT = 12
# Managed Money positions (available in disaggregated report)
COL_MANAGED_LONG = 15     # M_Money_Positions_Long_All
COL_MANAGED_SHORT = 16    # M_Money_Positions_Short_All


def _match_commodity(market_name: str) -> str | None:
    """Match a CFTC market name to our commodity_type."""
    upper = market_name.upper()
    for pattern, commodity in CFTC_MARKET_MAP.items():
        if pattern in upper:
            return commodity
    return None


def _safe_int(val: str) -> int:
    """Parse an integer from CSV, stripping whitespace."""
    try:
        return int(val.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return 0


def fetch_cftc_cot() -> list[dict]:
    """Download and parse the CFTC deacom.txt file."""
    logger.info("Fetching CFTC COT data from %s", CFTC_URL)
    resp = httpx.get(CFTC_URL, timeout=60, follow_redirects=True)
    resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader, None)  # skip header row
    if not header:
        logger.warning("CFTC COT file appears empty")
        return []

    records: list[dict] = []
    for row in reader:
        if len(row) < 17:
            continue

        commodity = _match_commodity(row[COL_MARKET_NAME])
        if not commodity:
            continue

        # Parse report date
        raw_date = row[COL_REPORT_DATE].strip()
        try:
            report_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            try:
                report_date = datetime.strptime(raw_date, "%y%m%d").date()
            except ValueError:
                logger.warning("Cannot parse COT date: %s", raw_date)
                continue

        open_interest = _safe_int(row[COL_OPEN_INTEREST])
        comm_long = _safe_int(row[COL_COMM_LONG])
        comm_short = _safe_int(row[COL_COMM_SHORT])
        noncomm_long = _safe_int(row[COL_NONCOMM_LONG])
        noncomm_short = _safe_int(row[COL_NONCOMM_SHORT])
        managed_long = _safe_int(row[COL_MANAGED_LONG])
        managed_short = _safe_int(row[COL_MANAGED_SHORT])

        records.append({
            "commodity": commodity,
            "report_date": report_date.isoformat(),
            "open_interest": open_interest,
            "commercial_net": comm_long - comm_short,
            "non_commercial_net": noncomm_long - noncomm_short,
            "managed_money_net": managed_long - managed_short,
        })

    logger.info("Parsed %d COT records for tracked commodities", len(records))
    return records


def ingest_cftc_cot() -> int:
    """Fetch and store CFTC COT data. Returns number of rows upserted."""
    records = fetch_cftc_cot()
    if not records:
        logger.info("No CFTC COT records to ingest")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cot_reports (
                    id BIGSERIAL PRIMARY KEY,
                    commodity TEXT NOT NULL,
                    report_date DATE NOT NULL,
                    open_interest INT NOT NULL DEFAULT 0,
                    commercial_net INT NOT NULL DEFAULT 0,
                    non_commercial_net INT NOT NULL DEFAULT 0,
                    managed_money_net INT NOT NULL DEFAULT 0,
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (commodity, report_date)
                )
            """)
            values = [
                (
                    r["commodity"], r["report_date"], r["open_interest"],
                    r["commercial_net"], r["non_commercial_net"], r["managed_money_net"],
                )
                for r in records
            ]
            execute_values(
                cur,
                """
                INSERT INTO cot_reports
                    (commodity, report_date, open_interest,
                     commercial_net, non_commercial_net, managed_money_net)
                VALUES %s
                ON CONFLICT (commodity, report_date) DO UPDATE SET
                    open_interest = EXCLUDED.open_interest,
                    commercial_net = EXCLUDED.commercial_net,
                    non_commercial_net = EXCLUDED.non_commercial_net,
                    managed_money_net = EXCLUDED.managed_money_net,
                    ingested_at = NOW()
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d CFTC COT records", len(records))
    finally:
        conn.close()

    return len(records)
