"""Forward curves ingestion via yfinance.

Fetches multiple contract months for key commodities (crude oil, natural gas, gold)
to build forward/futures curves. Called by Celery beat task `fetch_forward_curves` every 4h.
"""

import logging
from datetime import datetime, timezone

import psycopg2
import yfinance as yf

from config import settings

logger = logging.getLogger("forward_curves")

# CME month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun,
#                  N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
MONTH_CODES = ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Commodity root symbols → our commodity name
COMMODITY_ROOTS: dict[str, str] = {
    "CL": "crude_oil",
    "NG": "natural_gas",
    "GC": "gold",
}


def _build_contract_tickers(root: str, months_out: int = 12) -> list[dict]:
    """Build ticker symbols for the next N contract months.

    Returns list of dicts with ticker, contract_month label, and approximate expiry.
    """
    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month
    contracts = []

    for i in range(months_out):
        m = (month + i - 1) % 12  # 0-indexed month
        y = year + (month + i - 1) // 12
        code = MONTH_CODES[m]
        year_suffix = str(y)[-2:]  # e.g. "27"

        ticker = f"{root}{code}{year_suffix}.NYM" if root in ("CL", "NG") else f"{root}{code}{year_suffix}.CMX"
        contract_month = f"{MONTH_NAMES[m]} {y}"
        # Approximate expiry: 20th of the contract month
        expiry = datetime(y, m + 1, 20, tzinfo=timezone.utc)

        contracts.append({
            "ticker": ticker,
            "contract_month": contract_month,
            "expiry_date": expiry,
        })

    return contracts


def fetch_forward_curves() -> dict:
    """Fetch forward curve data for all configured commodities and store in DB."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    total_inserted = 0
    total_skipped = 0

    try:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS forward_curves (
                    id BIGSERIAL PRIMARY KEY,
                    commodity TEXT NOT NULL,
                    contract_month TEXT NOT NULL,
                    expiry_date TIMESTAMPTZ NOT NULL,
                    settlement_price DOUBLE PRECISION NOT NULL,
                    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (commodity, contract_month, time)
                )
            """)
            conn.commit()

            for root, commodity in COMMODITY_ROOTS.items():
                contracts = _build_contract_tickers(root)
                tickers = [c["ticker"] for c in contracts]

                logger.info("Fetching %d contracts for %s", len(tickers), commodity)

                try:
                    df = yf.download(tickers, period="1d", group_by="ticker", threads=True)
                except Exception as e:
                    logger.error("yfinance download failed for %s: %s", commodity, e)
                    total_skipped += len(tickers)
                    continue

                if df.empty:
                    logger.warning("Empty dataframe for %s", commodity)
                    total_skipped += len(tickers)
                    continue

                now = datetime.now(timezone.utc)

                for contract in contracts:
                    ticker = contract["ticker"]
                    try:
                        if len(tickers) == 1:
                            ticker_df = df
                        else:
                            ticker_df = df[ticker]

                        if ticker_df.empty:
                            total_skipped += 1
                            continue

                        last_row = ticker_df.iloc[-1]
                        close = last_row.get("Close")
                        if close is None:
                            total_skipped += 1
                            continue

                        price = float(close)
                        if price <= 0:
                            total_skipped += 1
                            continue

                        cur.execute(
                            """
                            INSERT INTO forward_curves (commodity, contract_month, expiry_date, settlement_price, time)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (commodity, contract_month, time) DO UPDATE
                                SET settlement_price = EXCLUDED.settlement_price,
                                    expiry_date = EXCLUDED.expiry_date
                            """,
                            (commodity, contract["contract_month"], contract["expiry_date"], price, now),
                        )
                        total_inserted += cur.rowcount

                    except (KeyError, TypeError, IndexError) as e:
                        logger.warning("Failed to parse %s for %s: %s", ticker, commodity, e)
                        total_skipped += 1

            conn.commit()

        logger.info("Forward curves: %d inserted, %d skipped", total_inserted, total_skipped)
        return {"inserted": total_inserted, "skipped": total_skipped}
    finally:
        conn.close()
