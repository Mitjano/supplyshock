"""Macro endpoints — /api/v1/macro/*

- GET /macro/rates         — Fed Funds, 10Y, yield curve (Issue #86)
- GET /macro/uncertainty   — Economic Policy Uncertainty (Issue #86)
- GET /macro/world-trade   — CPB World Trade Monitor (Issue #90)
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/macro", tags=["Macro"])


@router.get("/rates")
async def get_rates(
    indicator: str = Query(
        "all",
        description="Rate indicator: dxy, fed_funds, treasury_10y, yield_curve, all",
    ),
    days: int = Query(90, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Interest rates, DXY, and yield curve data from FRED."""
    indicator_map = {
        "dxy": "DTWEXBGS",
        "fed_funds": "DFF",
        "treasury_10y": "DGS10",
        "yield_curve": "T10Y2Y",
    }

    if indicator == "all":
        target_indicators = list(indicator_map.values())
    elif indicator in indicator_map:
        target_indicators = [indicator_map[indicator]]
    else:
        return {"error": f"Unknown indicator: {indicator}", "valid": list(indicator_map.keys()) + ["all"]}

    result = await db.execute(
        text(f"""
            SELECT indicator, time, value, unit, source
            FROM macro_indicators
            WHERE indicator = ANY(:indicators)
              AND time >= NOW() - INTERVAL '{days} days'
            ORDER BY indicator, time DESC
        """),
        {"indicators": target_indicators},
    )
    rows = result.mappings().all()

    # Group by indicator
    grouped: dict[str, list] = {}
    for r in rows:
        key = r["indicator"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "value": r["value"],
            "unit": r["unit"],
        })

    return {"data": grouped, "indicator": indicator, "days": days}


@router.get("/uncertainty")
async def get_uncertainty(
    days: int = Query(90, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Economic Policy Uncertainty Index and Industrial Production from FRED."""
    result = await db.execute(
        text(f"""
            SELECT indicator, time, value, unit, source
            FROM macro_indicators
            WHERE indicator IN ('USEPUINDXD', 'INDPRO')
              AND time >= NOW() - INTERVAL '{days} days'
            ORDER BY indicator, time DESC
        """),
    )
    rows = result.mappings().all()

    grouped: dict[str, list] = {}
    for r in rows:
        key = r["indicator"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "value": r["value"],
            "unit": r["unit"],
        })

    return {"data": grouped, "days": days}


@router.get("/world-trade")
async def get_world_trade(
    months: int = Query(24, ge=1, le=120, description="Number of months of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """CPB World Trade Monitor index data (Issue #90)."""
    result = await db.execute(
        text(f"""
            SELECT indicator, time, value, unit, source
            FROM macro_indicators
            WHERE indicator = 'world_trade_volume'
              AND source = 'cpb'
            ORDER BY time DESC
            LIMIT :months
        """),
        {"months": months},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "value": r["value"],
                "unit": r["unit"],
            }
            for r in rows
        ],
        "months": months,
    }
