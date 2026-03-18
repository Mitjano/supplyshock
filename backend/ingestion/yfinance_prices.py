"""Yahoo Finance futures price ingestion.

Downloads daily closing prices for commodity futures via yfinance.
Called by Celery beat task `ingest_yfinance_prices` every 4 hours.
"""

import logging
from datetime import datetime, timezone

import psycopg2
import yfinance as yf

from config import settings

logger = logging.getLogger("yfinance_prices")

# Yahoo Finance ticker → commodity name
TICKER_MAP: dict[str, str] = {
    "GC=F": "gold",
    "SI=F": "silver",
    "PL=F": "platinum",
    "PA=F": "palladium",
    "RB=F": "gasoline",
    "HO=F": "heating_oil",
    "ZC=F": "corn",
    "ZR=F": "rice",
    "CT=F": "cotton",
    "SB=F": "sugar",
    "KC=F": "coffee",
    "CC=F": "cocoa",
    "ZL=F": "soybean_oil",
    "ZM=F": "soybean_meal",
    "LE=F": "cattle",
    "LBS=F": "lumber",
}


def ingest_yfinance_prices() -> dict:
    """Batch-download latest futures prices and insert into commodity_prices."""
    tickers = list(TICKER_MAP.keys())
    logger.info("Downloading yfinance data for %d tickers", len(tickers))

    try:
        df = yf.download(tickers, period="2d", group_by="ticker", threads=True)
    except Exception as e:
        logger.error("yfinance download failed: %s", e)
        return {"error": str(e)}

    if df.empty:
        logger.warning("yfinance returned empty dataframe")
        return {"inserted": 0, "skipped": 0}

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        inserted = 0
        skipped = 0

        with conn.cursor() as cur:
            for ticker, commodity in TICKER_MAP.items():
                try:
                    # Handle both single and multi-ticker dataframe shapes
                    if len(tickers) == 1:
                        ticker_df = df
                    else:
                        ticker_df = df[ticker]

                    if ticker_df.empty:
                        skipped += 1
                        continue

                    for idx, row in ticker_df.iterrows():
                        close_price = row.get("Close")
                        if close_price is None or (hasattr(close_price, '__iter__') and len(close_price) == 0):
                            continue

                        price = float(close_price)
                        if price <= 0:
                            continue

                        # idx is a Timestamp from pandas
                        ts = idx.to_pydatetime().replace(tzinfo=timezone.utc)

                        cur.execute(
                            """
                            INSERT INTO commodity_prices (time, commodity, benchmark, price, currency, source)
                            VALUES (%s, %s, %s, %s, 'USD', 'yfinance')
                            ON CONFLICT (time, commodity, benchmark) DO NOTHING
                            """,
                            (ts, commodity, ticker, price),
                        )
                        inserted += cur.rowcount

                except (KeyError, TypeError) as e:
                    logger.warning("Failed to parse ticker %s: %s", ticker, e)
                    skipped += 1

            conn.commit()

        logger.info("yfinance ingest: %d inserted, %d skipped", inserted, skipped)
        return {"inserted": inserted, "skipped": skipped}
    finally:
        conn.close()
