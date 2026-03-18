"""Commodity correlation matrix computation.

Calculates Pearson correlation matrix of daily returns for all tracked
commodities.  Results cached in Redis with 1-hour TTL.

Issue #67
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "analytics:correlations"
CACHE_TTL = 3600  # 1 hour


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Compute Pearson correlation between two series (pure Python, no numpy)."""
    n = len(x)
    if n < 3 or n != len(y):
        return None

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        dy = y[i] - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    denom = math.sqrt(den_x * den_y)
    if denom == 0:
        return None
    return num / denom


def _daily_returns(prices: list[float]) -> list[float]:
    """Compute daily log returns from a price series."""
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0 and prices[i] > 0:
            returns.append(math.log(prices[i] / prices[i - 1]))
    return returns


async def compute_correlations(
    db: AsyncSession,
    window: str = "30d",
) -> dict:
    """Compute correlation matrix for all commodities in the given window.

    Returns {commodities: [...], matrix: [[...]]} where matrix[i][j]
    is the Pearson correlation between commodity i and j.
    """
    window_map = {"7d": 7, "30d": 30, "90d": 90}
    days = window_map.get(window, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Fetch daily closing prices for all commodities
    result = await db.execute(
        text("""
            SELECT commodity, DATE(time) as d, AVG(price) as avg_price
            FROM commodity_prices
            WHERE time >= :cutoff AND price > 0
            GROUP BY commodity, DATE(time)
            ORDER BY commodity, d
        """),
        {"cutoff": cutoff},
    )
    rows = result.mappings().all()

    # Group by commodity
    commodity_prices: dict[str, dict[str, float]] = {}
    for r in rows:
        comm = r["commodity"]
        if comm not in commodity_prices:
            commodity_prices[comm] = {}
        commodity_prices[comm][str(r["d"])] = float(r["avg_price"])

    commodities = sorted(commodity_prices.keys())
    if len(commodities) < 2:
        return {"commodities": commodities, "matrix": [], "window": window, "days": days}

    # Build aligned date set (dates present in ALL commodities)
    all_dates = set()
    for dates in commodity_prices.values():
        if not all_dates:
            all_dates = set(dates.keys())
        else:
            all_dates &= set(dates.keys())
    sorted_dates = sorted(all_dates)

    if len(sorted_dates) < 3:
        return {"commodities": commodities, "matrix": [], "window": window, "days": days}

    # Compute returns for each commodity
    returns_map: dict[str, list[float]] = {}
    for comm in commodities:
        prices = [commodity_prices[comm][d] for d in sorted_dates]
        returns_map[comm] = _daily_returns(prices)

    # Build correlation matrix
    n = len(commodities)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            corr = _pearson(returns_map[commodities[i]], returns_map[commodities[j]])
            val = round(corr, 4) if corr is not None else None
            matrix[i][j] = val
            matrix[j][i] = val

    return {
        "commodities": commodities,
        "matrix": matrix,
        "window": window,
        "days": days,
        "data_points": len(sorted_dates),
    }


async def get_correlations_cached(db: AsyncSession, redis_client, window: str = "30d") -> dict:
    """Return correlation matrix, using Redis cache if available."""
    cache_key = f"{REDIS_KEY_PREFIX}:{window}"

    # Try cache first
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass  # cache miss or error, compute fresh

    result = await compute_correlations(db, window)

    # Cache result
    if redis_client and result.get("matrix"):
        try:
            await redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL)
        except Exception:
            pass

    return result
