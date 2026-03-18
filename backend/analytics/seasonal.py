"""Seasonal pattern analysis for commodities.

Normalizes historical prices to day-of-year basis (Jan 1 = 100) and computes
percentile bands across multiple years.  Returns current year vs historical pattern.

Issue #68
"""

import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def compute_seasonal_pattern(
    db: AsyncSession,
    commodity: str,
    years: int = 5,
) -> dict:
    """Compute seasonal price pattern for a commodity.

    Returns:
        - current_year: list of {day_of_year, indexed_price} for the current year
        - historical: per day_of_year median/p25/p75/min/max from N years of data
    """
    now = datetime.now(timezone.utc)
    current_year = now.year
    cutoff = datetime(current_year - years, 1, 1, tzinfo=timezone.utc)

    # Fetch daily average prices
    result = await db.execute(
        text("""
            SELECT DATE(time) as d, AVG(price) as avg_price,
                   EXTRACT(YEAR FROM time)::INT as yr,
                   EXTRACT(DOY FROM time)::INT as doy
            FROM commodity_prices
            WHERE commodity = :commodity
              AND time >= :cutoff
              AND price > 0
            GROUP BY DATE(time), EXTRACT(YEAR FROM time), EXTRACT(DOY FROM time)
            ORDER BY d
        """),
        {"commodity": commodity, "cutoff": cutoff},
    )
    rows = result.mappings().all()

    if not rows:
        return {
            "commodity": commodity,
            "years": years,
            "current_year": [],
            "historical": [],
        }

    # Group prices by year, indexed to Jan 1 = 100
    yearly: dict[int, dict[int, float]] = {}  # year -> {doy -> indexed_price}
    jan1_prices: dict[int, float] = {}

    # First pass: find Jan 1 (or earliest) price per year for indexing
    for r in rows:
        yr = r["yr"]
        doy = r["doy"]
        price = float(r["avg_price"])
        if yr not in jan1_prices or doy < min(
            d for d in yearly.get(yr, {yr: {doy: price}})
        ):
            # Track earliest day seen per year
            pass
        if yr not in yearly:
            yearly[yr] = {}
        yearly[yr][doy] = price

    # Get the base price for each year (earliest available day)
    for yr, doy_prices in yearly.items():
        earliest_doy = min(doy_prices.keys())
        jan1_prices[yr] = doy_prices[earliest_doy]

    # Normalize to index = 100 at Jan 1
    indexed: dict[int, dict[int, float]] = {}
    for yr, doy_prices in yearly.items():
        base = jan1_prices.get(yr)
        if not base or base <= 0:
            continue
        indexed[yr] = {}
        for doy, price in doy_prices.items():
            indexed[yr][doy] = (price / base) * 100.0

    # Build historical percentile bands per day-of-year (from past years only)
    past_years = {yr: vals for yr, vals in indexed.items() if yr < current_year}
    historical_bands: list[dict] = []

    for doy in range(1, 367):
        values = []
        for yr_data in past_years.values():
            if doy in yr_data:
                values.append(yr_data[doy])
        if not values:
            continue

        values.sort()
        n = len(values)
        historical_bands.append({
            "day_of_year": doy,
            "median": _percentile(values, 50),
            "p25": _percentile(values, 25),
            "p75": _percentile(values, 75),
            "min": round(values[0], 2),
            "max": round(values[-1], 2),
            "years_with_data": n,
        })

    # Current year data
    current_data = []
    if current_year in indexed:
        for doy in sorted(indexed[current_year].keys()):
            current_data.append({
                "day_of_year": doy,
                "indexed_price": round(indexed[current_year][doy], 2),
            })

    return {
        "commodity": commodity,
        "years": years,
        "base_description": "Jan 1 (or earliest) = 100",
        "current_year": current_data,
        "historical": historical_bands,
    }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute percentile from a sorted list (linear interpolation)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return round(sorted_values[0], 2)

    k = (pct / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_values[int(k)], 2)

    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return round(d0 + d1, 2)
