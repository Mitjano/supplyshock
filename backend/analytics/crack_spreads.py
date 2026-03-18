"""Crack spread calculations.

Computes 3-2-1 crack spread: (2*gasoline + 1*heating_oil - 3*WTI) / 3
Runs every 4 hours via Celery Beat.

Issue #66
"""

import logging
from datetime import datetime, timezone

import psycopg2

from config import settings

logger = logging.getLogger(__name__)

# Benchmarks used for the 3-2-1 crack spread calculation
# Prices are stored in commodity_prices table with these benchmark names
CRACK_COMPONENTS = {
    "wti": {"commodity": "crude_oil", "benchmark": "WTI"},
    "gasoline": {"commodity": "gasoline", "benchmark": "RBOB"},
    "heating_oil": {"commodity": "heating_oil", "benchmark": "NY Harbor No.2"},
}

# Fallback benchmarks if primary not found
FALLBACK_BENCHMARKS = {
    "gasoline": [("diesel", "NY Harbor ULSD")],
    "heating_oil": [("diesel", "NY Harbor ULSD")],
}


def _get_latest_price(cur, commodity: str, benchmark: str) -> float | None:
    """Get latest price for a commodity/benchmark pair."""
    cur.execute(
        """
        SELECT price FROM commodity_prices
        WHERE commodity = %s AND benchmark = %s
        ORDER BY time DESC LIMIT 1
        """,
        (commodity, benchmark),
    )
    row = cur.fetchone()
    return float(row[0]) if row else None


def calculate_crack_spreads() -> dict:
    """Calculate and store 3-2-1 crack spread.

    Returns dict with spread value and components, or empty dict on failure.
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Fetch WTI
            wti = _get_latest_price(
                cur,
                CRACK_COMPONENTS["wti"]["commodity"],
                CRACK_COMPONENTS["wti"]["benchmark"],
            )
            if wti is None:
                logger.warning("No WTI price found for crack spread calculation")
                return {}

            # Fetch gasoline (with fallback)
            gasoline = _get_latest_price(
                cur,
                CRACK_COMPONENTS["gasoline"]["commodity"],
                CRACK_COMPONENTS["gasoline"]["benchmark"],
            )
            if gasoline is None:
                for fb_comm, fb_bench in FALLBACK_BENCHMARKS.get("gasoline", []):
                    gasoline = _get_latest_price(cur, fb_comm, fb_bench)
                    if gasoline is not None:
                        # Convert $/gallon to $/barrel (42 gal/bbl)
                        gasoline = gasoline * 42
                        break
            else:
                gasoline = gasoline * 42  # RBOB is $/gallon

            # Fetch heating oil (with fallback)
            heating_oil = _get_latest_price(
                cur,
                CRACK_COMPONENTS["heating_oil"]["commodity"],
                CRACK_COMPONENTS["heating_oil"]["benchmark"],
            )
            if heating_oil is None:
                for fb_comm, fb_bench in FALLBACK_BENCHMARKS.get("heating_oil", []):
                    heating_oil = _get_latest_price(cur, fb_comm, fb_bench)
                    if heating_oil is not None:
                        heating_oil = heating_oil * 42
                        break
            else:
                heating_oil = heating_oil * 42  # $/gallon → $/barrel

            if gasoline is None or heating_oil is None:
                logger.warning(
                    "Missing product prices for crack spread (gasoline=%s, heating_oil=%s)",
                    gasoline, heating_oil,
                )
                return {}

            # 3-2-1 crack spread: (2*gasoline + 1*heating_oil - 3*WTI) / 3
            spread = (2 * gasoline + heating_oil - 3 * wti) / 3
            now = datetime.now(timezone.utc)

            # Ensure table + store result
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crack_spreads (
                    id BIGSERIAL PRIMARY KEY,
                    time TIMESTAMPTZ NOT NULL,
                    spread_type TEXT NOT NULL DEFAULT '3-2-1',
                    wti_price DOUBLE PRECISION NOT NULL,
                    gasoline_price DOUBLE PRECISION NOT NULL,
                    heating_oil_price DOUBLE PRECISION NOT NULL,
                    spread_value DOUBLE PRECISION NOT NULL,
                    UNIQUE (spread_type, time)
                )
            """)
            cur.execute(
                """
                INSERT INTO crack_spreads
                    (time, spread_type, wti_price, gasoline_price, heating_oil_price, spread_value)
                VALUES (%s, '3-2-1', %s, %s, %s, %s)
                ON CONFLICT (spread_type, time) DO UPDATE SET
                    spread_value = EXCLUDED.spread_value,
                    wti_price = EXCLUDED.wti_price,
                    gasoline_price = EXCLUDED.gasoline_price,
                    heating_oil_price = EXCLUDED.heating_oil_price
                """,
                (now, wti, gasoline, heating_oil, round(spread, 4)),
            )
        conn.commit()

        result = {
            "time": now.isoformat(),
            "spread_type": "3-2-1",
            "wti": round(wti, 4),
            "gasoline_per_bbl": round(gasoline, 4),
            "heating_oil_per_bbl": round(heating_oil, 4),
            "spread": round(spread, 4),
        }
        logger.info("Crack spread calculated: $%.2f/bbl", spread)
        return result
    finally:
        conn.close()
