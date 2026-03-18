"""Voyage endpoints — /api/v1/voyages/*

- GET /voyages          — list/filter voyages
- GET /voyages/{id}     — voyage detail
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/voyages", tags=["Voyages"])


@router.get("")
async def list_voyages(
    mmsi: int | None = Query(None, description="Filter by vessel MMSI"),
    status: str | None = Query(None, description="underway, arrived, completed, floating_storage"),
    cargo_type: str | None = Query(None, description="Filter by cargo commodity"),
    vessel_type: str | None = Query(None),
    origin_port_id: str | None = Query(None),
    dest_port_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List voyages with filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if mmsi is not None:
        conditions.append("v.mmsi = :mmsi")
        params["mmsi"] = mmsi

    if status:
        conditions.append("v.status = :status::voyage_status")
        params["status"] = status

    if cargo_type:
        conditions.append("v.cargo_type = :cargo_type")
        params["cargo_type"] = cargo_type

    if vessel_type:
        conditions.append("v.vessel_type = :vessel_type::vessel_type")
        params["vessel_type"] = vessel_type

    if origin_port_id:
        conditions.append("v.origin_port_id = :origin_port_id")
        params["origin_port_id"] = origin_port_id

    if dest_port_id:
        conditions.append("v.dest_port_id = :dest_port_id")
        params["dest_port_id"] = dest_port_id

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM voyages v {where}"),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT v.id, v.mmsi, v.imo, v.vessel_name, v.vessel_type,
                   v.origin_port_id, v.dest_port_id,
                   v.departure_time, v.arrival_time,
                   v.status, v.laden_status, v.cargo_type,
                   v.volume_estimate, v.distance_nm,
                   op.name AS origin_port_name,
                   op.country_code AS origin_country,
                   dp.name AS dest_port_name,
                   dp.country_code AS dest_country,
                   v.created_at
            FROM voyages v
            LEFT JOIN ports op ON op.id = v.origin_port_id
            LEFT JOIN ports dp ON dp.id = v.dest_port_id
            {where}
            ORDER BY v.departure_time DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [_format_voyage(row) for row in rows],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/{voyage_id}")
async def get_voyage(
    voyage_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get voyage detail by ID."""
    result = await db.execute(
        text("""
            SELECT v.id, v.mmsi, v.imo, v.vessel_name, v.vessel_type,
                   v.origin_port_id, v.dest_port_id,
                   v.departure_time, v.arrival_time,
                   v.status, v.laden_status, v.cargo_type,
                   v.volume_estimate, v.distance_nm,
                   op.name AS origin_port_name,
                   op.country_code AS origin_country,
                   dp.name AS dest_port_name,
                   dp.country_code AS dest_country,
                   v.created_at
            FROM voyages v
            LEFT JOIN ports op ON op.id = v.origin_port_id
            LEFT JOIN ports dp ON dp.id = v.dest_port_id
            WHERE v.id = :voyage_id
        """),
        {"voyage_id": voyage_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Voyage not found")

    return {"data": _format_voyage(row)}


def _format_voyage(row) -> dict[str, Any]:
    """Format a voyage row into API response dict."""
    return {
        "id": str(row["id"]),
        "mmsi": row["mmsi"],
        "imo": row["imo"],
        "vessel_name": row["vessel_name"],
        "vessel_type": row["vessel_type"],
        "origin": {
            "port_id": str(row["origin_port_id"]) if row["origin_port_id"] else None,
            "name": row["origin_port_name"],
            "country_code": row["origin_country"],
        } if row["origin_port_id"] else None,
        "destination": {
            "port_id": str(row["dest_port_id"]) if row["dest_port_id"] else None,
            "name": row["dest_port_name"],
            "country_code": row["dest_country"],
        } if row["dest_port_id"] else None,
        "departure_time": row["departure_time"].isoformat() if row["departure_time"] else None,
        "arrival_time": row["arrival_time"].isoformat() if row["arrival_time"] else None,
        "status": row["status"],
        "laden_status": row["laden_status"],
        "cargo_type": row["cargo_type"],
        "volume_estimate": float(row["volume_estimate"]) if row["volume_estimate"] else None,
        "distance_nm": float(row["distance_nm"]) if row["distance_nm"] else None,
        "created_at": row["created_at"].isoformat(),
    }
