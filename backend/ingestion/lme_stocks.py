"""LME warehouse stock proxy ingestion via yfinance metal ETFs.

Uses metal ETFs as proxies for LME warehouse stock movements:
- JJM (iPath Bloomberg Industrial Metals ETN) — broad metals
- CPER (United States Copper Index Fund) — copper

Stores in warehouse_stocks table (auto-created).
Runs daily via Celery Beat.

Issue #90
"""

import logging
from datetime import datetime, timezone

import psycopg2
import yfinance as yf

from config import settings

logger = logging.getLogger(__name__)

# ETF proxies for warehouse stocks
METAL_ETFS = {
    "JJM": {"metal": "industrial_metals", "description": "Bloomberg Industrial Metals ETN"},
    "CPER": {"metal": "copper", "description": "US Copper Index Fund"},
    "SLV": {"metal": "silver", "description": "iShares Silver Trust"},
    "GLD": {"metal": "gold", "description": "SPDR Gold Shares"},
}


def _ensure_warehouse_table(conn) -> None:
    """Create warehouse_stocks table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS warehouse_stocks (
                id BIGSERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                metal TEXT NOT NULL,
                etf_ticker TEXT NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                volume BIGINT,
                source TEXT NOT NULL DEFAULT 'yfinance',
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (metal, etf_ticker, time)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_warehouse_stocks_metal_time
            ON warehouse_stocks (metal, time DESC)
        """)
    conn.commit()


def ingest_lme_stocks() -> int:
    """Fetch metal ETF data as warehouse stock proxies."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    inserted = 0

    try:
        _ensure_warehouse_table(conn)

        for ticker_symbol, config in METAL_ETFS.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="5d", interval="1d")

                if hist.empty:
                    logger.warning("No data for %s", ticker_symbol)
                    continue

                with conn.cursor() as cur:
                    for ts, row in hist.iterrows():
                        price = float(row["Close"])
                        volume = int(row["Volume"]) if row["Volume"] else None

                        dt = ts.to_pydatetime()
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)

                        cur.execute(
                            """
                            INSERT INTO warehouse_stocks
                                (time, metal, etf_ticker, price, volume, source)
                            VALUES (%s, %s, %s, %s, %s, 'yfinance')
                            ON CONFLICT (metal, etf_ticker, time) DO UPDATE SET
                                price = EXCLUDED.price,
                                volume = EXCLUDED.volume,
                                ingested_at = NOW()
                            """,
                            (dt, config["metal"], ticker_symbol, price, volume),
                        )
                        inserted += cur.rowcount

                conn.commit()
                logger.info("%s (%s): fetched %d days", ticker_symbol, config["metal"], len(hist))

            except Exception as e:
                logger.error("Failed to fetch %s: %s", ticker_symbol, e)

    finally:
        conn.close()

    logger.info("Warehouse stocks: total %d records inserted/updated", inserted)
    return inserted
