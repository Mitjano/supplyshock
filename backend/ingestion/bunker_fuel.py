"""Bunker fuel proxy price ingestion.

Uses yfinance for:
- HO=F (NYMEX heating oil futures) as proxy for IFO 380 / VLSFO
- DDFUELUSGULF from FRED as proxy for MGO (diesel)

Converts $/barrel to $/metric tonne using 7.45 bbl/mt factor.
Stores in bunker_prices table (auto-created).
Runs every 6h via Celery Beat.

Issue #87
"""

import logging
from datetime import datetime, timezone

import psycopg2
import requests
import yfinance as yf

from config import settings

logger = logging.getLogger(__name__)

# Conversion: ~7.45 barrels per metric tonne for fuel oil
BBL_PER_MT = 7.45

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


def _ensure_bunker_table(conn) -> None:
    """Create bunker_prices table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bunker_prices (
                id BIGSERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                fuel_type TEXT NOT NULL,
                price_per_mt DOUBLE PRECISION NOT NULL,
                price_per_bbl DOUBLE PRECISION,
                source_ticker TEXT,
                currency TEXT NOT NULL DEFAULT 'USD',
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (fuel_type, time)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_bunker_prices_fuel_time
            ON bunker_prices (fuel_type, time DESC)
        """)
    conn.commit()


def ingest_bunker_fuel_prices() -> int:
    """Fetch bunker fuel proxy prices and store in bunker_prices."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    inserted = 0

    try:
        _ensure_bunker_table(conn)

        # ── 1. Heating oil futures (HO=F) as VLSFO proxy ──
        try:
            ho = yf.Ticker("HO=F")
            hist = ho.history(period="5d", interval="1d")

            with conn.cursor() as cur:
                for ts, row in hist.iterrows():
                    # HO=F is in $/gallon, convert to $/barrel (42 gal/bbl) then $/mt
                    price_per_gallon = float(row["Close"])
                    price_per_bbl = price_per_gallon * 42.0
                    price_per_mt = price_per_bbl * BBL_PER_MT

                    dt = ts.to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    cur.execute(
                        """
                        INSERT INTO bunker_prices
                            (time, fuel_type, price_per_mt, price_per_bbl, source_ticker, currency)
                        VALUES (%s, %s, %s, %s, %s, 'USD')
                        ON CONFLICT (fuel_type, time) DO UPDATE SET
                            price_per_mt = EXCLUDED.price_per_mt,
                            price_per_bbl = EXCLUDED.price_per_bbl,
                            ingested_at = NOW()
                        """,
                        (dt, "vlsfo_proxy", round(price_per_mt, 2), round(price_per_bbl, 2), "HO=F"),
                    )
                    inserted += cur.rowcount

            conn.commit()
            logger.info("Heating oil (VLSFO proxy): inserted %d records", inserted)

        except Exception as e:
            logger.error("HO=F fetch failed: %s", e)

        # ── 2. FRED diesel price (DDFUELUSGULF) as MGO proxy ──
        api_key = getattr(settings, "FRED_API_KEY", "")
        if api_key:
            try:
                resp = requests.get(
                    FRED_API_URL,
                    params={
                        "series_id": "DDFUELUSGULF",
                        "api_key": api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 10,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    observations = resp.json().get("observations", [])
                    with conn.cursor() as cur:
                        for obs in observations:
                            value = obs.get("value", ".")
                            if value == "." or not value:
                                continue
                            try:
                                price_per_gallon = float(value)
                            except (ValueError, TypeError):
                                continue

                            price_per_bbl = price_per_gallon * 42.0
                            price_per_mt = price_per_bbl * BBL_PER_MT

                            dt = datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

                            cur.execute(
                                """
                                INSERT INTO bunker_prices
                                    (time, fuel_type, price_per_mt, price_per_bbl, source_ticker, currency)
                                VALUES (%s, %s, %s, %s, %s, 'USD')
                                ON CONFLICT (fuel_type, time) DO UPDATE SET
                                    price_per_mt = EXCLUDED.price_per_mt,
                                    price_per_bbl = EXCLUDED.price_per_bbl,
                                    ingested_at = NOW()
                                """,
                                (dt, "mgo_proxy", round(price_per_mt, 2), round(price_per_bbl, 2), "DDFUELUSGULF"),
                            )
                            inserted += cur.rowcount

                    conn.commit()
                    logger.info("Diesel (MGO proxy): inserted records from FRED")

            except Exception as e:
                logger.error("FRED diesel fetch failed: %s", e)
        else:
            logger.warning("FRED_API_KEY not set — skipping MGO proxy")

    finally:
        conn.close()

    logger.info("Bunker fuel: total %d records inserted/updated", inserted)
    return inserted
