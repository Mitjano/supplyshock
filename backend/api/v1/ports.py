"""Port endpoints — /api/v1/ports/*

- GET /ports         — list/filter ports (bbox, major, commodity)
- GET /ports/{id}    — port detail
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

router = APIRouter(prefix="/ports", tags=["Ports"])


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@router.get("")
async def list_ports(
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    is_major: bool | None = Query(None),
    commodity: str | None = Query(None, description="Filter by commodity in commodities array"),
    limit: int = Query(500, le=5000),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """List ports with optional filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox format", "code": "INVALID_BBOX"})
        try:
            min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
            conditions.append("latitude BETWEEN :min_lat AND :max_lat")
            conditions.append("longitude BETWEEN :min_lng AND :max_lng")
            params.update(min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox values", "code": "INVALID_BBOX"})

    if is_major is not None:
        conditions.append("is_major = :is_major")
        params["is_major"] = is_major

    if commodity:
        conditions.append(":commodity = ANY(commodities)")
        params["commodity"] = commodity

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT id, wpi_number, name, country_code, latitude, longitude,
                   region, harbor_type, commodities, annual_throughput_mt,
                   is_major, is_chokepoint
            FROM ports
            {where}
            ORDER BY is_major DESC, name ASC
            LIMIT :limit
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "wpi_number": row["wpi_number"],
                "name": row["name"],
                "country_code": row["country_code"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "region": row["region"],
                "harbor_type": row["harbor_type"],
                "commodities": row["commodities"] or [],
                "annual_throughput_mt": float(row["annual_throughput_mt"]) if row["annual_throughput_mt"] else None,
                "is_major": row["is_major"],
                "is_chokepoint": row["is_chokepoint"],
            }
            for row in rows
        ],
        "meta": {"total": len(rows), "limit": limit},
    }
