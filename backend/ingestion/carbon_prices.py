"""Carbon price ingestion via yfinance KRBN ETF.

Uses KRBN (KraneShares Global Carbon Strategy ETF) as proxy
for EU ETS carbon prices. Stores in commodity_prices table.
Runs every 6h via Celery Beat.

Issue #85
"""

import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import yfinance as yf

from config import settings

logger = logging.getLogger(__name__)


def ingest_carbon_prices() -> int:
    """Fetch KRBN ETF data as EU ETS carbon price proxy."""
    try:
        ticker = yf.Ticker("KRBN")
        hist = ticker.history(period="5d", interval="1d")

        if hist.empty:
            logger.warning("No KRBN data returned from yfinance")
            return 0

        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
        inserted = 0
        try:
            with conn.cursor() as cur:
                for ts, row in hist.iterrows():
                    price = float(row["Close"])
                    if price <= 0:
                        continue

                    # Convert pandas Timestamp to datetime
                    dt = ts.to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    cur.execute(
                        """
                        INSERT INTO commodity_prices
                            (time, commodity, benchmark, price, currency, source)
                        VALUES (%s, %s, %s, %s, 'USD', %s)
                        ON CONFLICT (time, commodity, benchmark) DO NOTHING
                        """,
                        (dt, "carbon_eu_ets", "KRBN", price, "yfinance"),
                    )
                    inserted += cur.rowcount

            conn.commit()
            logger.info("Carbon prices: inserted %d records", inserted)
        finally:
            conn.close()

        return inserted

    except Exception as e:
        logger.error("Carbon price ingestion failed: %s", e)
        return 0
