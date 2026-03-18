"""Google Trends commodity search interest ingestion.

Uses pytrends for commodity-related search interest data.
Stores in macro_indicators table.
Runs every 6h via Celery Beat (with graceful failure — pytrends is fragile).

Issue #89
"""

import logging
from datetime import datetime, timezone

import psycopg2

from config import settings

logger = logging.getLogger(__name__)

TREND_KEYWORDS = [
    "oil price",
    "gold price",
    "gas price",
    "wheat price",
    "copper price",
    "coal price",
]


def ingest_google_trends() -> int:
    """Fetch Google Trends data for commodity keywords.

    NOTE: pytrends is rate-limited and may fail. This task handles
    failures gracefully and should not block other ingestion.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.error("pytrends not installed — skipping Google Trends ingestion")
        return 0

    inserted = 0

    try:
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 30))

        # Fetch interest over time for all keywords (max 5 per request)
        for batch_start in range(0, len(TREND_KEYWORDS), 5):
            batch = TREND_KEYWORDS[batch_start : batch_start + 5]

            try:
                pytrends.build_payload(batch, cat=0, timeframe="today 3-m")
                df = pytrends.interest_over_time()

                if df.empty:
                    logger.info("No Google Trends data for batch: %s", batch)
                    continue

                conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
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

                        for keyword in batch:
                            if keyword not in df.columns:
                                continue

                            for ts, row in df.iterrows():
                                value = float(row[keyword])
                                dt = ts.to_pydatetime()
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)

                                indicator_name = f"gtrends_{keyword.replace(' ', '_')}"
                                cur.execute(
                                    """
                                    INSERT INTO macro_indicators
                                        (indicator, time, value, unit, source)
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (indicator, time, source) DO UPDATE SET
                                        value = EXCLUDED.value,
                                        ingested_at = NOW()
                                    """,
                                    (indicator_name, dt, value, "index_0_100", "google_trends"),
                                )
                                inserted += cur.rowcount

                    conn.commit()
                finally:
                    conn.close()

                logger.info("Google Trends batch %s: inserted %d records", batch, inserted)

            except Exception as e:
                logger.warning("Google Trends batch failed (non-fatal): %s — %s", batch, e)
                continue

    except Exception as e:
        logger.warning("Google Trends ingestion failed (non-fatal): %s", e)

    return inserted
