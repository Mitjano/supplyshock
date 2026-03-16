"""Nasdaq Data Link (Quandl) price ingestion for metals and agriculture.

Fetches copper (LME), iron ore, aluminium, nickel, wheat, soybeans
every 1 hour via Celery Beat.
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

NASDAQ_BASE_URL = "https://data.nasdaq.com/api/v3/datasets"

# Nasdaq Data Link dataset codes
NASDAQ_SERIES = {
    "copper": {"dataset": "LME/PR_CU", "benchmark": "LME", "commodity": "copper", "unit": "tonne"},
    "iron_ore": {"dataset": "ODA/PIORECR_USD", "benchmark": "TSI 62% Fe", "commodity": "iron_ore", "unit": "tonne"},
    "aluminium": {"dataset": "LME/PR_AL", "benchmark": "LME", "commodity": "aluminium", "unit": "tonne"},
    "nickel": {"dataset": "LME/PR_NI", "benchmark": "LME", "commodity": "nickel", "unit": "tonne"},
    "wheat": {"dataset": "CHRIS/CME_W1", "benchmark": "CME", "commodity": "wheat", "unit": "bushel"},
    "soybeans": {"dataset": "CHRIS/CME_S1", "benchmark": "CME", "commodity": "soybeans", "unit": "bushel"},
}


def fetch_nasdaq_prices() -> list[dict]:
    """Fetch latest prices from Nasdaq Data Link."""
    api_key = settings.NASDAQ_DATA_LINK_API_KEY

    if not api_key:
        logger.warning("NASDAQ_DATA_LINK_API_KEY not set — using fallback prices")
        return _fallback_prices()

    prices = []
    for key, config in NASDAQ_SERIES.items():
        try:
            resp = httpx.get(
                f"{NASDAQ_BASE_URL}/{config['dataset']}.json",
                params={"api_key": api_key, "rows": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            dataset = data.get("dataset", {})
            rows = dataset.get("data", [])
            if rows:
                latest = rows[0]
                # Price is in column 1 (after date in column 0)
                price = float(latest[1]) if len(latest) > 1 else 0
                if price <= 0:
                    logger.warning("Invalid price for %s: %s", key, latest)
                    continue
                prices.append({
                    "commodity": config["commodity"],
                    "benchmark": config["benchmark"],
                    "price": price,
                    "currency": "USD",
                    "unit": config["unit"],
                    "source": "nasdaq_data_link",
                    "time": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.warning("Nasdaq fetch failed for %s: %s", key, e)

    if not prices:
        return _fallback_prices()

    return prices


def _fallback_prices() -> list[dict]:
    """Fallback prices for development/demo."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"commodity": "copper", "benchmark": "LME", "price": 8950.00, "currency": "USD", "unit": "tonne", "source": "fallback", "time": now},
        {"commodity": "iron_ore", "benchmark": "TSI 62% Fe", "price": 108.50, "currency": "USD", "unit": "tonne", "source": "fallback", "time": now},
        {"commodity": "aluminium", "benchmark": "LME", "price": 2380.00, "currency": "USD", "unit": "tonne", "source": "fallback", "time": now},
        {"commodity": "nickel", "benchmark": "LME", "price": 16200.00, "currency": "USD", "unit": "tonne", "source": "fallback", "time": now},
        {"commodity": "wheat", "benchmark": "CME", "price": 5.82, "currency": "USD", "unit": "bushel", "source": "fallback", "time": now},
        {"commodity": "soybeans", "benchmark": "CME", "price": 11.45, "currency": "USD", "unit": "bushel", "source": "fallback", "time": now},
    ]


def ingest_nasdaq_prices():
    """Fetch and store Nasdaq prices in commodity_prices table."""
    prices = fetch_nasdaq_prices()
    if not prices:
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            values = [
                (p["time"], p["commodity"], p["benchmark"], p["price"], p["currency"], p["unit"], p["source"])
                for p in prices
            ]
            execute_values(
                cur,
                """
                INSERT INTO commodity_prices (time, commodity, benchmark, price, currency, unit, source)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d Nasdaq prices", len(prices))
    finally:
        conn.close()

    return len(prices)
