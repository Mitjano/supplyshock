"""Chokepoint endpoints — /api/v1/chokepoints/* (Issue #76)

- GET /chokepoints/imf — IMF PortWatch chokepoint transit data
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/chokepoints", tags=["Chokepoints"])


@router.get("/imf")
async def get_imf_chokepoint_data(
    name: str = Query(..., description="Chokepoint: suez, panama, hormuz, malacca, bosporus, gibraltar, dover, cape"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """IMF PortWatch chokepoint transit data.

    Returns daily transit counts, average volume, and trend for a chokepoint.
    """
    # days is validated as int (1-365) by Query, safe to interpolate
    result = await db.execute(
        text(f"""
            SELECT transit_date, vessel_count, total_teu, total_tonnes
            FROM chokepoint_transits
            WHERE node_id = :name
              AND transit_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY transit_date DESC
        """),
        {"name": name},
    )
    rows = result.mappings().all()

    if not rows:
        return {
            "data": [],
            "chokepoint": name,
            "days": days,
            "summary": {"avg_vessels": 0, "avg_teu": 0, "avg_tonnes": 0, "trend": "unknown"},
        }

    daily_transits = [
        {
            "date": str(r["transit_date"]),
            "vessel_count": r["vessel_count"],
            "total_teu": r["total_teu"],
            "total_tonnes": r["total_tonnes"],
        }
        for r in rows
    ]

    # Calculate summary statistics
    vessel_counts = [r["vessel_count"] or 0 for r in rows]
    teu_values = [r["total_teu"] or 0 for r in rows]
    tonnes_values = [r["total_tonnes"] or 0 for r in rows]

    avg_vessels = sum(vessel_counts) / len(vessel_counts) if vessel_counts else 0
    avg_teu = sum(teu_values) / len(teu_values) if teu_values else 0
    avg_tonnes = sum(tonnes_values) / len(tonnes_values) if tonnes_values else 0

    # Trend: compare first half vs second half
    mid = len(vessel_counts) // 2
    if mid > 0:
        recent_avg = sum(vessel_counts[:mid]) / mid  # rows are DESC, so first = recent
        older_avg = sum(vessel_counts[mid:]) / len(vessel_counts[mid:])
        if older_avg > 0:
            change_pct = (recent_avg - older_avg) / older_avg * 100
            if change_pct > 5:
                trend = "increasing"
            elif change_pct < -5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"
    else:
        trend = "unknown"

    return {
        "data": daily_transits,
        "chokepoint": name,
        "days": days,
        "summary": {
            "avg_vessels": round(avg_vessels, 1),
            "avg_teu": round(avg_teu, 1),
            "avg_tonnes": round(avg_tonnes, 1),
            "trend": trend,
        },
    }
