"""Nasdaq Data Link (Quandl) price ingestion for metals and agriculture.

Fetches copper, iron ore, aluminium, nickel, wheat, soybeans
every 1 hour via Celery Beat.

Uses yfinance as fallback for datasets that require premium access or are deprecated.
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
# Note: CHRIS/* datasets are deprecated. We use available alternatives where possible
# and fall back to yfinance for unavailable datasets.
NASDAQ_SERIES = {
    "iron_ore": {
        "dataset": "ODA/PIORECR_USD",
        "price_column": "Value",  # ODA datasets use "Value" column
        "benchmark": "TSI 62% Fe",
        "commodity": "iron_ore",
        "unit": "tonne",
    },
}

# Series fetched via yfinance (Yahoo Finance) as fallback
# These cover datasets that are deprecated or require premium on Nasdaq Data Link
YFINANCE_SERIES = {
    # ── Metals ──
    "copper": {
        "ticker": "HG=F",
        "benchmark": "COMEX",
        "commodity": "copper",
        "unit": "tonne",
        "multiplier": 22.0462,  # cents/lb -> USD/tonne (2204.62 lb/tonne / 100)
    },
    "aluminium": {
        "ticker": "ALI=F",
        "benchmark": "COMEX",
        "commodity": "aluminium",
        "unit": "tonne",
    },
    "nickel": {
        "ticker": "^SPGSNI",  # S&P GSCI Nickel Index as proxy
        "benchmark": "LME",
        "commodity": "nickel",
        "unit": "tonne",
    },
    "gold": {
        "ticker": "GC=F",
        "benchmark": "COMEX",
        "commodity": "gold",
        "unit": "troy_oz",
    },
    "silver": {
        "ticker": "SI=F",
        "benchmark": "COMEX",
        "commodity": "silver",
        "unit": "troy_oz",
    },
    "platinum": {
        "ticker": "PL=F",
        "benchmark": "NYMEX",
        "commodity": "platinum",
        "unit": "troy_oz",
    },
    "palladium": {
        "ticker": "PA=F",
        "benchmark": "NYMEX",
        "commodity": "palladium",
        "unit": "troy_oz",
    },
    "zinc": {
        "ticker": "^SPGSZN",  # S&P GSCI Zinc proxy
        "benchmark": "LME",
        "commodity": "zinc",
        "unit": "tonne",
    },
    "tin": {
        "ticker": "^SPGSSN",  # S&P GSCI Tin proxy
        "benchmark": "LME",
        "commodity": "tin",
        "unit": "tonne",
    },
    "lead": {
        "ticker": "^SPGSLP",  # S&P GSCI Lead proxy
        "benchmark": "LME",
        "commodity": "lead",
        "unit": "tonne",
    },
    # ── Energy ──
    "coal": {
        "ticker": "MTF=F",  # Newcastle coal futures
        "benchmark": "ICE",
        "commodity": "coal",
        "unit": "tonne",
    },
    "natural_gas": {
        "ticker": "NG=F",
        "benchmark": "NYMEX",
        "commodity": "natural_gas",
        "unit": "mmbtu",
    },
    "gasoline": {
        "ticker": "RB=F",
        "benchmark": "NYMEX",
        "commodity": "gasoline",
        "unit": "gallon",
    },
    "heating_oil": {
        "ticker": "HO=F",
        "benchmark": "NYMEX",
        "commodity": "heating_oil",
        "unit": "gallon",
    },
    # ── Agriculture ──
    "wheat": {
        "ticker": "ZW=F",
        "benchmark": "CME",
        "commodity": "wheat",
        "unit": "bushel",
    },
    "soybeans": {
        "ticker": "ZS=F",
        "benchmark": "CME",
        "commodity": "soybeans",
        "unit": "bushel",
    },
    "corn": {
        "ticker": "ZC=F",
        "benchmark": "CME",
        "commodity": "corn",
        "unit": "bushel",
    },
    "rice": {
        "ticker": "ZR=F",
        "benchmark": "CME",
        "commodity": "rice",
        "unit": "cwt",
    },
    "cotton": {
        "ticker": "CT=F",
        "benchmark": "ICE",
        "commodity": "cotton",
        "unit": "lb",
    },
    "coffee": {
        "ticker": "KC=F",
        "benchmark": "ICE",
        "commodity": "coffee",
        "unit": "lb",
    },
    "sugar": {
        "ticker": "SB=F",
        "benchmark": "ICE",
        "commodity": "sugar",
        "unit": "lb",
    },
    "cocoa": {
        "ticker": "CC=F",
        "benchmark": "ICE",
        "commodity": "cocoa",
        "unit": "tonne",
    },
    "palm_oil": {
        "ticker": "FCPO=F",  # Bursa Malaysia palm oil futures
        "benchmark": "MDEX",
        "commodity": "palm_oil",
        "unit": "tonne",
    },
    "lumber": {
        "ticker": "LBS=F",
        "benchmark": "CME",
        "commodity": "lumber",
        "unit": "mbf",
    },
    "rubber": {
        "ticker": "^SPGSRU",  # S&P GSCI proxy
        "benchmark": "TOCOM",
        "commodity": "rubber",
        "unit": "kg",
    },
}


def _fetch_nasdaq_prices(api_key: str) -> list[dict]:
    """Fetch prices from Nasdaq Data Link for available datasets."""
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
            columns = dataset.get("column_names", [])

            if rows and columns:
                latest = rows[0]

                # Find the correct price column by name
                price_col = config.get("price_column", "Value")
                col_idx = None
                for i, col_name in enumerate(columns):
                    if col_name.lower() == price_col.lower():
                        col_idx = i
                        break
                    # Fallback: look for Settlement/Close/Last
                    if col_name.lower() in ("settle", "settlement", "close", "last", "value"):
                        col_idx = i

                if col_idx is None or col_idx >= len(latest):
                    logger.warning("Could not find price column for %s in columns: %s", key, columns)
                    continue

                price = float(latest[col_idx]) if latest[col_idx] is not None else 0
                if price <= 0:
                    logger.warning("Invalid price for %s: %s", key, latest)
                    continue

                # Use actual data date from column 0 (always the date column)
                data_date = latest[0] if latest[0] else None
                try:
                    price_time = datetime.strptime(data_date, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError):
                    logger.warning("Could not parse date '%s' for %s, using current time", data_date, key)
                    price_time = datetime.now(timezone.utc).isoformat()

                prices.append({
                    "commodity": config["commodity"],
                    "benchmark": config["benchmark"],
                    "price": price,
                    "currency": "USD",
                    "unit": config["unit"],
                    "source": "nasdaq_data_link",
                    "time": price_time,
                })
        except Exception as e:
            logger.error("Nasdaq fetch failed for %s: %s", key, e)

    return prices


def _fetch_yfinance_prices() -> list[dict]:
    """Fetch prices via yfinance for commodities not available on Nasdaq Data Link."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — cannot fetch fallback prices. pip install yfinance")
        return []

    prices = []
    for key, config in YFINANCE_SERIES.items():
        try:
            ticker = yf.Ticker(config["ticker"])
            hist = ticker.history(period="5d")

            if hist.empty:
                logger.warning("No yfinance data for %s (%s)", key, config["ticker"])
                continue

            latest = hist.iloc[-1]
            price = float(latest["Close"])

            # Apply unit conversion multiplier if specified
            multiplier = config.get("multiplier")
            if multiplier:
                price *= multiplier

            if price <= 0:
                logger.warning("Invalid yfinance price for %s: %s", key, price)
                continue

            # Use the actual date from yfinance index
            price_time = latest.name.to_pydatetime().replace(tzinfo=timezone.utc).isoformat()

            prices.append({
                "commodity": config["commodity"],
                "benchmark": config["benchmark"],
                "price": round(price, 2),
                "currency": "USD",
                "unit": config["unit"],
                "source": "yfinance",
                "time": price_time,
            })
        except Exception as e:
            logger.error("yfinance fetch failed for %s: %s", key, e)

    return prices


def fetch_nasdaq_prices() -> list[dict]:
    """Fetch latest prices from Nasdaq Data Link and yfinance fallbacks."""
    api_key = settings.NASDAQ_DATA_LINK_API_KEY

    prices = []

    if api_key:
        prices.extend(_fetch_nasdaq_prices(api_key))
    else:
        logger.warning("NASDAQ_DATA_LINK_API_KEY not set — skipping Nasdaq datasets")

    # Always try yfinance for commodities not covered by Nasdaq
    prices.extend(_fetch_yfinance_prices())

    if not prices:
        logger.error("No prices fetched from any source")

    return prices


def ingest_nasdaq_prices():
    """Fetch and store prices in commodity_prices table."""
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
        logger.info("Ingested %d commodity prices", len(prices))
    finally:
        conn.close()

    return len(prices)
