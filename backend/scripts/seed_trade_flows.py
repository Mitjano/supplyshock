"""Seed trade flows from UN Comtrade API for top 5 commodities.

Usage:
    docker compose exec backend python scripts/seed_trade_flows.py

Downloads top 20 trade routes per commodity and inserts into trade_flows table.
"""

import logging

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HS commodity codes for our 5 tracked commodities
COMMODITY_HS_CODES = {
    "crude_oil": "2709",   # Crude petroleum
    "coal": "2701",        # Coal
    "iron_ore": "2601",    # Iron ores
    "copper": "2603",      # Copper ores
    "lng": "2711",         # Petroleum gases (LNG)
}

COMTRADE_BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A"


def fetch_trade_flows(commodity: str, hs_code: str, api_key: str | None) -> list[dict]:
    """Fetch top trade routes for a commodity from UN Comtrade.

    Returns list of dicts: {origin, destination, volume_mt, value_usd}
    """
    params = {
        "cmdCode": hs_code,
        "flowCode": "X",  # Exports
        "period": "2023",  # Latest full year
        "reporterCode": "all",
        "partnerCode": "all",
        "maxRecords": 500,
    }
    headers = {}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key

    try:
        resp = httpx.get(COMTRADE_BASE_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Comtrade API failed for %s: %s — using fallback data", commodity, e)
        return _fallback_flows(commodity)

    records = data.get("data", [])
    if not records:
        logger.warning("No Comtrade data for %s — using fallback", commodity)
        return _fallback_flows(commodity)

    flows = []
    for rec in records:
        reporter = rec.get("reporterISO", "")
        partner = rec.get("partnerISO", "")
        if not reporter or not partner or partner == "W00":
            continue

        flows.append({
            "commodity": commodity,
            "origin_country": reporter[:2],
            "destination_country": partner[:2],
            "volume_mt": rec.get("netWgt", 0) / 1000 if rec.get("netWgt") else None,  # kg → mt
            "value_usd": rec.get("primaryValue", 0),
            "period_year": 2023,
            "source": "un_comtrade",
        })

    # Sort by volume and keep top 20
    flows.sort(key=lambda x: x.get("volume_mt") or 0, reverse=True)
    return flows[:20]


def _fallback_flows(commodity: str) -> list[dict]:
    """Hardcoded fallback trade flows for demo/offline use."""
    fallbacks = {
        "crude_oil": [
            ("SA", "CN", 80_000, 45_000_000),
            ("SA", "JP", 35_000, 20_000_000),
            ("RU", "CN", 70_000, 38_000_000),
            ("IQ", "IN", 45_000, 25_000_000),
            ("AE", "JP", 25_000, 14_000_000),
            ("US", "KR", 20_000, 12_000_000),
            ("NO", "GB", 15_000, 9_000_000),
            ("BR", "CN", 30_000, 17_000_000),
            ("NG", "IN", 18_000, 10_000_000),
            ("KW", "KR", 12_000, 7_000_000),
        ],
        "coal": [
            ("AU", "CN", 90_000, 8_000_000),
            ("AU", "JP", 70_000, 6_000_000),
            ("AU", "IN", 55_000, 5_000_000),
            ("ID", "CN", 120_000, 9_000_000),
            ("ID", "IN", 80_000, 6_500_000),
            ("ZA", "IN", 25_000, 2_000_000),
            ("RU", "CN", 40_000, 3_500_000),
            ("US", "IN", 15_000, 1_500_000),
            ("CO", "NL", 12_000, 1_200_000),
            ("MZ", "IN", 8_000, 700_000),
        ],
        "iron_ore": [
            ("AU", "CN", 700_000, 80_000_000),
            ("BR", "CN", 250_000, 28_000_000),
            ("AU", "JP", 60_000, 7_000_000),
            ("AU", "KR", 45_000, 5_000_000),
            ("BR", "NL", 20_000, 2_500_000),
            ("ZA", "CN", 40_000, 4_500_000),
            ("IN", "CN", 30_000, 3_500_000),
            ("CA", "CN", 15_000, 1_800_000),
            ("SE", "DE", 10_000, 1_200_000),
            ("UA", "CN", 12_000, 1_400_000),
        ],
        "copper": [
            ("CL", "CN", 8_000, 30_000_000),
            ("PE", "CN", 5_000, 18_000_000),
            ("AU", "CN", 2_000, 7_500_000),
            ("CL", "JP", 3_000, 11_000_000),
            ("ID", "CN", 2_500, 9_000_000),
            ("CD", "CN", 1_500, 5_500_000),
            ("ZM", "CN", 1_200, 4_500_000),
            ("PE", "KR", 1_000, 3_800_000),
            ("CL", "KR", 1_500, 5_500_000),
            ("MX", "US", 800, 3_000_000),
        ],
        "lng": [
            ("AU", "JP", 35_000, 15_000_000),
            ("QA", "KR", 20_000, 9_000_000),
            ("QA", "JP", 15_000, 7_000_000),
            ("US", "GB", 12_000, 5_500_000),
            ("US", "NL", 10_000, 4_500_000),
            ("AU", "CN", 25_000, 11_000_000),
            ("MY", "JP", 8_000, 3_500_000),
            ("NG", "ES", 5_000, 2_300_000),
            ("QA", "IN", 8_000, 3_600_000),
            ("US", "ES", 6_000, 2_800_000),
        ],
    }

    rows = fallbacks.get(commodity, [])
    return [
        {
            "commodity": commodity,
            "origin_country": r[0],
            "destination_country": r[1],
            "volume_mt": r[2],
            "value_usd": r[3],
            "period_year": 2023,
            "source": "fallback_estimate",
        }
        for r in rows
    ]


def seed_trade_flows():
    """Seed trade flows for all 5 commodities."""
    api_key = settings.COMTRADE_API_KEY if hasattr(settings, "COMTRADE_API_KEY") else None

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    total = 0

    try:
        for commodity, hs_code in COMMODITY_HS_CODES.items():
            logger.info("Fetching trade flows for %s (HS %s)...", commodity, hs_code)
            flows = fetch_trade_flows(commodity, hs_code, api_key)

            if not flows:
                continue

            values = [
                (
                    f["commodity"], f["origin_country"], f["destination_country"],
                    f["volume_mt"], f["value_usd"], f["period_year"], None, f["source"],
                )
                for f in flows
            ]

            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO trade_flows (commodity, origin_country, destination_country,
                                             volume_mt, value_usd, period_year, period_month, source)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                    """,
                    values,
                )
            conn.commit()
            total += len(values)
            logger.info("  Inserted %d flows for %s", len(values), commodity)

    finally:
        conn.close()

    return total


if __name__ == "__main__":
    count = seed_trade_flows()
    logger.info("Done! Seeded %d trade flows total", count)
