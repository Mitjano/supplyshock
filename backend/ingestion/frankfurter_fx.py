"""Frankfurter FX rate ingestion (Issue #78).

Fetches currency exchange rates from Frankfurter API (free, unlimited).
Includes DXY proxy calculation from a USD basket.

Celery Beat: every 4 hours.
"""

import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

from config import settings

logger = logging.getLogger("frankfurter_fx")

FRANKFURTER_BASE = "https://api.frankfurter.dev"

# 14 USD currency pairs to track
USD_PAIRS = [
    "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD",
    "NZD", "SEK", "NOK", "SGD", "HKD", "KRW", "INR",
]

# DXY basket weights (approximation of ICE US Dollar Index)
# Real DXY: EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%
DXY_WEIGHTS = {
    "EUR": 0.576,
    "JPY": 0.136,
    "GBP": 0.119,
    "CAD": 0.091,
    "SEK": 0.042,
    "CHF": 0.036,
}


def _ensure_table(conn):
    """Create fx_rates table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fx_rates (
                id BIGSERIAL PRIMARY KEY,
                pair TEXT NOT NULL,
                rate_date DATE NOT NULL,
                rate DOUBLE PRECISION NOT NULL,
                source TEXT NOT NULL DEFAULT 'frankfurter',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (pair, rate_date)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date
            ON fx_rates (pair, rate_date DESC)
        """)
    conn.commit()


def _calculate_dxy(rates: dict[str, float]) -> float | None:
    """Calculate DXY proxy from USD rates.

    DXY = 50.14348112 * PRODUCT(rate^weight) for each basket currency.
    Since Frankfurter gives USD/X rates, we invert for X/USD where needed.
    """
    try:
        product = 1.0
        for currency, weight in DXY_WEIGHTS.items():
            rate = rates.get(currency)
            if rate is None or rate == 0:
                return None
            # Frankfurter gives 1 USD = X units of currency
            # DXY uses the inverse for EUR (USD per EUR) but direct for others
            if currency == "EUR":
                # EUR is quoted as EUR/USD in DXY, so use inverse
                product *= (1.0 / rate) ** weight
            else:
                product *= rate ** weight
        return round(50.14348112 * product, 4)
    except Exception as e:
        logger.error("DXY calculation failed: %s", e)
        return None


def _fetch_fx_rates(days: int = 30) -> dict[str, dict[str, float]]:
    """Fetch historical FX rates from Frankfurter API.

    Returns {date_str: {currency: rate, ...}, ...}
    """
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        url = f"{FRANKFURTER_BASE}/{start_date}..{end_date}"
        params = {
            "from": "USD",
            "to": ",".join(USD_PAIRS),
        }
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            logger.error("Frankfurter API returned %d", resp.status_code)
            return {}

        data = resp.json()
        return data.get("rates", {})
    except Exception as e:
        logger.error("Failed to fetch Frankfurter FX rates: %s", e)
        return {}


def ingest_frankfurter_fx():
    """Ingest FX rates from Frankfurter API."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        total = 0

        rates_by_date = _fetch_fx_rates(days=30)
        if not rates_by_date:
            logger.warning("No FX data received from Frankfurter API")
            return {"records_ingested": 0}

        with conn.cursor() as cur:
            for date_str, rates in rates_by_date.items():
                # Insert individual currency pairs
                for currency, rate in rates.items():
                    pair = f"USD/{currency}"
                    try:
                        cur.execute("""
                            INSERT INTO fx_rates (pair, rate_date, rate, source)
                            VALUES (%s, %s, %s, 'frankfurter')
                            ON CONFLICT (pair, rate_date)
                            DO UPDATE SET rate = EXCLUDED.rate
                        """, (pair, date_str, rate))
                        total += 1
                    except Exception as e:
                        logger.warning("Failed to upsert FX %s/%s: %s", pair, date_str, e)
                        conn.rollback()
                        continue

                # Calculate and store DXY proxy
                dxy = _calculate_dxy(rates)
                if dxy is not None:
                    try:
                        cur.execute("""
                            INSERT INTO fx_rates (pair, rate_date, rate, source)
                            VALUES ('DXY', %s, %s, 'calculated')
                            ON CONFLICT (pair, rate_date)
                            DO UPDATE SET rate = EXCLUDED.rate
                        """, (date_str, dxy))
                        total += 1
                    except Exception as e:
                        logger.warning("Failed to upsert DXY/%s: %s", date_str, e)
                        conn.rollback()

            conn.commit()

        logger.info("Frankfurter FX ingestion complete: %d records", total)
        return {"records_ingested": total}
    finally:
        conn.close()
