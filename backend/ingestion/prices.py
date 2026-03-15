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
    "copper": {"dataset": "LME/PR_CU", "benchmark": "LME", "commodity": "copper"},
    "iron_ore": {"dataset": "ODA/PIORECR_USD", "benchmark": "TSI 62% Fe", "commodity": "iron_ore"},
    "aluminium": {"dataset": "LME/PR_AL", "benchmark": "LME", "commodity": "aluminium"},
    "nickel": {"dataset": "LME/PR_NI", "benchmark": "LME", "commodity": "nickel"},
    "wheat": {"dataset": "CHRIS/CME_W1", "benchmark": "CME", "commodity": "wheat"},
    "soybeans": {"dataset": "CHRIS/CME_S1", "benchmark": "CME", "commodity": "soybeans"},
}


def fetch_nasdaq_prices() -> list[dict]:
    """Fetch latest prices from Nasdaq Data Link."""
    api_key = getattr(settings, "NASDAQ_API_KEY", "") or getattr(settings, "COMTRADE_API_KEY", "")

    if not api_key:
        logger.warning("NASDAQ_API_KEY not set — using fallback prices")
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
                # Price is usually in column 1 (after date in column 0)
                price = float(latest[1]) if len(latest) > 1 else 0
                prices.append({
                    "commodity": config["commodity"],
                    "benchmark": config["benchmark"],
                    "price_usd": price,
                    "currency": "USD",
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
        {"commodity": "copper", "benchmark": "LME", "price_usd": 8950.00, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "iron_ore", "benchmark": "TSI 62% Fe", "price_usd": 108.50, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "aluminium", "benchmark": "LME", "price_usd": 2380.00, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "nickel", "benchmark": "LME", "price_usd": 16200.00, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "wheat", "benchmark": "CME", "price_usd": 5.82, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "soybeans", "benchmark": "CME", "price_usd": 11.45, "currency": "USD", "source": "fallback", "time": now},
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
                (p["time"], p["commodity"], p["benchmark"], p["price_usd"], p["currency"], p["source"])
                for p in prices
            ]
            execute_values(
                cur,
                """
                INSERT INTO commodity_prices (time, commodity, benchmark, price_usd, currency, source)
                VALUES %s
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d Nasdaq prices", len(prices))
    finally:
        conn.close()

    return len(prices)
