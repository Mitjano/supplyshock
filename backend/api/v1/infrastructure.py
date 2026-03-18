"""Infrastructure endpoints — /api/v1/infrastructure/*

- GET /infrastructure — list infrastructure assets within bbox
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/infrastructure", tags=["Infrastructure"])


@router.get("")
async def list_infrastructure(
    type: str | None = Query(None, description="Filter: lng_terminal, refinery, pipeline, coal_mine, oil_field, storage, coal_port"),
    bbox: str | None = Query(None, description="lat1,lon1,lat2,lon2 (min_lat,min_lon,max_lat,max_lon)"),
    commodity: str | None = Query(None, description="Filter by commodity: crude_oil, lng, coal, iron_ore, copper"),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, le=1000),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List infrastructure assets with optional bbox, type, and commodity filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if type:
        conditions.append("ia.type = :type")
        params["type"] = type

    if commodity:
        conditions.append(":commodity = ANY(ia.commodities)")
        params["commodity"] = commodity

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid bbox format — expected lat1,lon1,lat2,lon2", "code": "INVALID_BBOX"},
            )
        try:
            min_lat, min_lon, max_lat, max_lon = [float(p) for p in parts]
            conditions.append("ia.latitude BETWEEN :min_lat AND :max_lat")
            conditions.append("ia.longitude BETWEEN :min_lon AND :max_lon")
            params.update(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid bbox values — expected numbers", "code": "INVALID_BBOX"},
            )

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM infrastructure_assets ia {where}"),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT ia.id, ia.type, ia.name, ia.latitude, ia.longitude,
                   ia.status, ia.capacity, ia.capacity_unit,
                   ia.commodities, ia.country_code, ia.description
            FROM infrastructure_assets ia
            {where}
            ORDER BY ia.name
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "type": r["type"],
                "name": r["name"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "status": r["status"],
                "capacity": float(r["capacity"]) if r["capacity"] else None,
                "capacity_unit": r["capacity_unit"],
                "commodities": r["commodities"],
                "country_code": r["country_code"],
                "description": r["description"],
            }
            for r in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }
