"""EIA (Energy Information Administration) price ingestion.

Fetches crude oil (WTI, Brent), LNG (Henry Hub), and coal (API2 proxy)
prices every 6 hours via Celery Beat.
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

EIA_BASE_URL = "https://api.eia.gov/v2"

# EIA series IDs for energy commodities
EIA_SERIES = {
    "crude_oil_wti": {"series": "PET.RWTC.D", "benchmark": "WTI", "commodity": "crude_oil"},
    "crude_oil_brent": {"series": "PET.RBRTE.D", "benchmark": "Brent", "commodity": "crude_oil"},
    "lng_henry_hub": {"series": "NG.RNGWHHD.D", "benchmark": "Henry Hub", "commodity": "lng"},
}


def fetch_eia_prices() -> list[dict]:
    """Fetch latest prices from EIA API."""
    api_key = settings.EIA_API_KEY
    if not api_key:
        logger.warning("EIA_API_KEY not set — using fallback prices")
        return _fallback_eia_prices()

    prices = []
    for key, config in EIA_SERIES.items():
        try:
            resp = httpx.get(
                f"{EIA_BASE_URL}/seriesid/{config['series']}",
                params={"api_key": api_key, "num": 5},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            series_data = data.get("response", {}).get("data", [])
            if series_data:
                latest = series_data[0]
                prices.append({
                    "commodity": config["commodity"],
                    "benchmark": config["benchmark"],
                    "price_usd": float(latest.get("value", 0)),
                    "currency": "USD",
                    "source": "eia",
                    "time": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.warning("EIA fetch failed for %s: %s", key, e)

    if not prices:
        return _fallback_eia_prices()

    return prices


def _fallback_eia_prices() -> list[dict]:
    """Fallback prices for development/demo without API key."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"commodity": "crude_oil", "benchmark": "WTI", "price_usd": 78.50, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "crude_oil", "benchmark": "Brent", "price_usd": 82.30, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "lng", "benchmark": "Henry Hub", "price_usd": 2.85, "currency": "USD", "source": "fallback", "time": now},
        {"commodity": "coal", "benchmark": "API2", "price_usd": 115.00, "currency": "USD", "source": "fallback", "time": now},
    ]


def ingest_eia_prices():
    """Fetch and store EIA prices in commodity_prices table."""
    prices = fetch_eia_prices()
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
        logger.info("Ingested %d EIA prices", len(prices))
    finally:
        conn.close()

    return len(prices)
