"""Crop endpoints — /api/v1/crops/*

- GET /crops/progress    — USDA crop progress & condition
- GET /crops/exports     — USDA weekly export sales

Issue #84
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/crops", tags=["Crops"])


@router.get("/progress")
async def get_crop_progress(
    commodity: str = Query(..., description="Commodity: corn, wheat, soybeans, cotton, sorghum"),
    data_type: str = Query("progress_planted", description="Data type: progress_planted, condition_good"),
    year: int | None = Query(None, description="Filter by year (default: all)"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """USDA crop progress and condition data."""
    conditions = ["commodity = :commodity", "data_type = :data_type"]
    params: dict[str, Any] = {"commodity": commodity.lower(), "data_type": data_type}

    if year:
        conditions.append("year = :year")
        params["year"] = year

    where = " AND ".join(conditions)

    result = await db.execute(
        text(f"""
            SELECT commodity, data_type, week_ending, year, value, unit, state, source
            FROM crop_data
            WHERE {where}
            ORDER BY week_ending DESC
            LIMIT 100
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "commodity": r["commodity"],
                "data_type": r["data_type"],
                "week_ending": r["week_ending"],
                "year": r["year"],
                "value": r["value"],
                "unit": r["unit"],
                "state": r["state"],
                "source": r["source"],
            }
            for r in rows
        ],
        "commodity": commodity,
        "data_type": data_type,
    }


@router.get("/exports")
async def get_export_sales(
    commodity: str = Query(..., description="Commodity: wheat, corn, soybeans, cotton, sorghum"),
    weeks: int = Query(12, ge=1, le=52, description="Number of weeks of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """USDA weekly export sales data."""
    result = await db.execute(
        text("""
            SELECT commodity, data_type, week_ending, year, value, unit, state, source
            FROM crop_data
            WHERE commodity = :commodity
              AND data_type = 'export_sales'
            ORDER BY week_ending DESC
            LIMIT :weeks
        """),
        {"commodity": commodity.lower(), "weeks": weeks},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "commodity": r["commodity"],
                "week_ending": r["week_ending"],
                "year": r["year"],
                "value": r["value"],
                "unit": r["unit"],
                "destination": r["state"],
                "source": r["source"],
            }
            for r in rows
        ],
        "commodity": commodity,
        "weeks": weeks,
    }
