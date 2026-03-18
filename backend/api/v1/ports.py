"""Port endpoints — /api/v1/ports/*

- GET /ports              — list/filter ports (bbox, major, commodity)
- GET /ports/{id}         — port detail
- GET /ports/{id}/vessels — vessels currently in port geofence
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from geo.geofence import get_vessels_in_port
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/ports", tags=["Ports"])


@router.get("")
async def list_ports(
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    is_major: bool | None = Query(None),
    commodity: str | None = Query(None, description="Filter by commodity in commodities array"),
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=5000),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
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

    params["offset"] = offset

    # Get total count
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM ports {where}"),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, wpi_number, name, country_code, latitude, longitude,
                   region, harbor_type, commodities, annual_throughput_mt,
                   radius_km, is_major, is_chokepoint
            FROM ports
            {where}
            ORDER BY is_major DESC, name ASC
            LIMIT :limit OFFSET :offset
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
                "radius_km": float(row["radius_km"]) if row["radius_km"] else 5.0,
                "is_major": row["is_major"],
                "is_chokepoint": row["is_chokepoint"],
            }
            for row in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/{port_id}")
async def get_port(
    port_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get port detail by ID."""
    result = await db.execute(
        text("""
            SELECT id, wpi_number, name, country_code, latitude, longitude,
                   region, harbor_type, max_vessel_size, commodities,
                   annual_throughput_mt, radius_km, unlocode, is_major, is_chokepoint
            FROM ports WHERE id = :port_id
        """),
        {"port_id": port_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Port not found")

    return {
        "id": str(row["id"]),
        "wpi_number": row["wpi_number"],
        "name": row["name"],
        "country_code": row["country_code"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "region": row["region"],
        "harbor_type": row["harbor_type"],
        "max_vessel_size": row["max_vessel_size"],
        "commodities": row["commodities"] or [],
        "annual_throughput_mt": float(row["annual_throughput_mt"]) if row["annual_throughput_mt"] else None,
        "radius_km": float(row["radius_km"]) if row["radius_km"] else 5.0,
        "unlocode": row["unlocode"],
        "is_major": row["is_major"],
        "is_chokepoint": row["is_chokepoint"],
    }


@router.get("/{port_id}/vessels")
async def list_vessels_in_port(
    port_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get vessels currently within a port's geofence radius.

    Uses PostGIS ST_DWithin against latest_vessel_positions.
    """
    # Verify port exists
    port_check = await db.execute(
        text("SELECT id, name FROM ports WHERE id = :port_id"),
        {"port_id": port_id},
    )
    if not port_check.mappings().first():
        raise HTTPException(status_code=404, detail="Port not found")

    vessels = await get_vessels_in_port(db, port_id)

    return {
        "data": vessels,
        "meta": {"port_id": port_id, "vessel_count": len(vessels)},
    }
