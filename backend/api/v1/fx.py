"""FX rate endpoints — /api/v1/fx/* (Issue #78)

- GET /fx     — currency pair rates
- GET /fx/dxy — US Dollar Index proxy
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/fx", tags=["FX Rates"])


@router.get("")
async def get_fx_rates(
    pairs: str = Query("USD/EUR", description="Comma-separated pairs: USD/EUR, USD/CNY, USD/JPY"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """FX rate time series from Frankfurter API."""
    pair_list = [p.strip() for p in pairs.split(",")]

    # days is validated as int (1-365) by Query, safe to interpolate
    result = await db.execute(
        text(f"""
            SELECT pair, rate_date, rate, source
            FROM fx_rates
            WHERE pair = ANY(:pairs)
              AND rate_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY pair, rate_date DESC
        """),
        {"pairs": pair_list},
    )
    rows = result.mappings().all()

    # Group by pair
    by_pair: dict[str, list] = {}
    for r in rows:
        p = r["pair"]
        if p not in by_pair:
            by_pair[p] = []
        by_pair[p].append({
            "date": str(r["rate_date"]),
            "rate": r["rate"],
        })

    # Calculate change statistics for each pair
    summaries = {}
    for p, values in by_pair.items():
        if len(values) >= 2:
            latest = values[0]["rate"]
            oldest = values[-1]["rate"]
            change = latest - oldest
            change_pct = (change / oldest * 100) if oldest else 0
            summaries[p] = {
                "latest": latest,
                "change": round(change, 6),
                "change_pct": round(change_pct, 4),
            }

    return {
        "data": by_pair,
        "summaries": summaries,
        "pairs": pair_list,
        "days": days,
    }


@router.get("/dxy")
async def get_dxy_index(
    days: int = Query(90, ge=1, le=730, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """US Dollar Index (DXY) proxy calculated from Frankfurter FX basket.

    Basket weights: EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%
    """
    # days is validated as int (1-730) by Query, safe to interpolate
    result = await db.execute(
        text(f"""
            SELECT rate_date, rate
            FROM fx_rates
            WHERE pair = 'DXY'
              AND rate_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY rate_date DESC
        """),
    )
    rows = result.mappings().all()

    data = [
        {
            "date": str(r["rate_date"]),
            "value": r["rate"],
        }
        for r in rows
    ]

    # Summary stats
    if data:
        values = [d["value"] for d in data]
        current = values[0]
        high = max(values)
        low = min(values)
        avg = sum(values) / len(values)
        change = values[0] - values[-1] if len(values) >= 2 else 0
        change_pct = (change / values[-1] * 100) if len(values) >= 2 and values[-1] else 0
    else:
        current = high = low = avg = change = change_pct = 0

    return {
        "data": data,
        "days": days,
        "summary": {
            "current": round(current, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "average": round(avg, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
        },
    }
