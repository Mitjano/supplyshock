"""EIA (Energy Information Administration) price ingestion.

Fetches crude oil (WTI, Brent) and natural gas (Henry Hub)
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

# EIA API v2 series configuration
# v2 uses route-based paths + facets instead of v1 series IDs
EIA_SERIES = {
    "crude_oil_wti": {
        "route": "petroleum/pri/spt",
        "facet_series": "RWTC",
        "frequency": "daily",
        "benchmark": "WTI",
        "commodity": "crude_oil",
        "unit": "barrel",
    },
    "crude_oil_brent": {
        "route": "petroleum/pri/spt",
        "facet_series": "RBRTE",
        "frequency": "daily",
        "benchmark": "Brent",
        "commodity": "crude_oil",
        "unit": "barrel",
    },
    "lng_henry_hub": {
        "route": "natural-gas/pri/sum",
        "facet_series": "RNGWHHD",
        "frequency": "daily",
        "benchmark": "Henry Hub",
        "commodity": "lng",
        "unit": "mmbtu",
    },
    "diesel": {
        "route": "petroleum/pri/spt",
        "facet_series": "EER_EPD2F_PF4_Y35NY_DPG",
        "frequency": "daily",
        "benchmark": "NY Harbor ULSD",
        "commodity": "diesel",
        "unit": "gallon",
    },
    "jet_fuel": {
        "route": "petroleum/pri/spt",
        "facet_series": "EER_EPJK_PF4_RGC_DPG",
        "frequency": "daily",
        "benchmark": "US Gulf Coast",
        "commodity": "jet_fuel",
        "unit": "gallon",
    },
}


def fetch_eia_prices() -> list[dict]:
    """Fetch latest prices from EIA API v2."""
    api_key = settings.EIA_API_KEY
    if not api_key:
        logger.error("EIA_API_KEY not set — skipping EIA price ingestion")
        return []

    prices = []
    for key, config in EIA_SERIES.items():
        try:
            url = f"{EIA_BASE_URL}/{config['route']}/data/"
            resp = httpx.get(
                url,
                params={
                    "api_key": api_key,
                    "frequency": config["frequency"],
                    "data[0]": "value",
                    "facets[series][]": config["facet_series"],
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "length": 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            series_data = data.get("response", {}).get("data", [])
            if series_data:
                latest = series_data[0]
                value = latest.get("value")
                if value is None:
                    logger.warning("EIA returned null value for %s", key)
                    continue

                price = float(value)
                if price <= 0:
                    logger.warning("EIA returned non-positive price for %s: %s", key, price)
                    continue

                # Use the period from API response as the price timestamp
                period = latest.get("period", "")
                try:
                    # EIA daily periods are formatted as YYYY-MM-DD
                    price_time = datetime.strptime(period, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError):
                    logger.warning("Could not parse period '%s' for %s, using current time", period, key)
                    price_time = datetime.now(timezone.utc).isoformat()

                prices.append({
                    "commodity": config["commodity"],
                    "benchmark": config["benchmark"],
                    "price": price,
                    "currency": "USD",
                    "unit": config["unit"],
                    "source": "eia",
                    "time": price_time,
                })
        except Exception as e:
            logger.error("EIA fetch failed for %s: %s", key, e)

    return prices


def ingest_eia_prices():
    """Fetch and store EIA prices in commodity_prices table."""
    prices = fetch_eia_prices()
    if not prices:
        logger.info("No EIA prices fetched — nothing to ingest")
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
        logger.info("Ingested %d EIA prices", len(prices))
    finally:
        conn.close()

    return len(prices)
