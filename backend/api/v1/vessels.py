"""Vessel endpoints — /api/v1/vessels/*

- GET  /vessels          — live vessel positions (bbox + type filter)
- GET  /vessels/{mmsi}   — full vessel detail
- GET  /vessels/{mmsi}/trail — vessel trail (last N hours)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/vessels", tags=["Vessels"])


@router.get("")
async def list_vessels(
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    vessel_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=5000),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get current vessel positions for the map viewport.

    Uses latest_vessel_positions materialized view for performance.
    Falls back to direct query if view doesn't exist yet.
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox format — expected min_lng,min_lat,max_lng,max_lat", "code": "INVALID_BBOX"})
        try:
            min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
            conditions.append("latitude BETWEEN :min_lat AND :max_lat")
            conditions.append("longitude BETWEEN :min_lng AND :max_lng")
            params.update(min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox values — expected numbers", "code": "INVALID_BBOX"})

    if vessel_type:
        conditions.append("vessel_type = :vessel_type")
        params["vessel_type"] = vessel_type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params["offset"] = offset

    # Get total count
    try:
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM latest_vessel_positions {where}"),
            params,
        )
        total = count_result.scalar()
    except Exception:
        count_result = await db.execute(
            text(f"""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ON (mmsi) mmsi
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '2 hours'
                ) sub
                {where}
            """),
            params,
        )
        total = count_result.scalar()

    # Try materialized view first, fall back to subquery
    try:
        result = await db.execute(
            text(f"""
                SELECT mmsi, imo, vessel_name, vessel_type, latitude, longitude,
                       speed_knots, course, destination, flag_country, time
                FROM latest_vessel_positions
                {where}
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
    except Exception:
        # Materialized view doesn't exist yet — use window function fallback
        result = await db.execute(
            text(f"""
                SELECT mmsi, imo, vessel_name, vessel_type, latitude, longitude,
                       speed_knots, course, destination, flag_country, time
                FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY time DESC) as rn
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '2 hours'
                ) sub
                WHERE rn = 1
                {' AND ' + ' AND '.join(conditions) if conditions else ''}
                LIMIT :limit OFFSET :offset
            """),
            params,
        )

    rows = result.mappings().all()

    return {
        "data": [
            {
                "mmsi": row["mmsi"],
                "imo": row["imo"],
                "vessel_name": row["vessel_name"],
                "vessel_type": row["vessel_type"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
                "course": float(row["course"]) if row["course"] else None,
                "destination": row["destination"],
                "flag_country": row["flag_country"],
                "time": row["time"].isoformat(),
            }
            for row in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/{mmsi}")
async def get_vessel_detail(
    mmsi: int,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get full vessel details by MMSI.

    Combines latest position from vessel_positions with static data
    from vessel_static_data (AIS Type 5: dimensions, DWT, callsign).
    Returns 404 if vessel hasn't been seen in the last 2 hours.
    """
    result = await db.execute(
        text("""
            SELECT vp.mmsi, vp.imo, vp.vessel_name, vp.vessel_type,
                   vp.latitude, vp.longitude,
                   vp.speed_knots, vp.course, vp.heading,
                   vp.destination, vp.eta, vp.draught,
                   vp.flag_country, vp.cargo_type, vp.time,
                   vs.callsign, vs.length_m, vs.beam_m,
                   vs.dwt_estimate, vs.max_draught,
                   vs.dim_a, vs.dim_b, vs.dim_c, vs.dim_d
            FROM vessel_positions vp
            LEFT JOIN vessel_static_data vs ON vs.mmsi = vp.mmsi
            WHERE vp.mmsi = :mmsi AND vp.time > NOW() - INTERVAL '2 hours'
            ORDER BY vp.time DESC
            LIMIT 1
        """),
        {"mmsi": mmsi},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "Vessel not found in last 2 hours", "code": "VESSEL_NOT_FOUND"},
        )

    data = {
        "mmsi": row["mmsi"],
        "imo": row["imo"],
        "vessel_name": row["vessel_name"],
        "vessel_type": row["vessel_type"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
        "course": float(row["course"]) if row["course"] else None,
        "heading": float(row["heading"]) if row["heading"] else None,
        "destination": row["destination"],
        "eta": row["eta"].isoformat() if row["eta"] else None,
        "draught": float(row["draught"]) if row["draught"] else None,
        "flag_country": row["flag_country"],
        "cargo_type": row["cargo_type"],
        "time": row["time"].isoformat(),
        # Static data from AIS Type 5 (may be NULL if not yet received)
        "callsign": row["callsign"],
        "length_m": float(row["length_m"]) if row["length_m"] else None,
        "beam_m": float(row["beam_m"]) if row["beam_m"] else None,
        "dwt_estimate": float(row["dwt_estimate"]) if row["dwt_estimate"] else None,
        "max_draught": float(row["max_draught"]) if row["max_draught"] else None,
    }

    return {"data": data}


@router.get("/{mmsi}/ownership")
async def get_vessel_ownership(
    mmsi: int,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get vessel ownership and classification details from vessel_static_data."""
    result = await db.execute(
        text("""
            SELECT vs.mmsi, vs.imo, vs.vessel_name, vs.callsign,
                   vs.owner, vs.operator, vs.classification_society,
                   vs.year_built, vs.gross_tonnage, vs.dwt_estimate,
                   vs.length_m, vs.beam_m, vs.max_draught,
                   vs.flag_country, vs.vessel_type
            FROM vessel_static_data vs
            WHERE vs.mmsi = :mmsi
        """),
        {"mmsi": mmsi},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "Vessel static data not found", "code": "VESSEL_NOT_FOUND"},
        )

    return {
        "data": {
            "mmsi": row["mmsi"],
            "imo": row["imo"],
            "vessel_name": row["vessel_name"],
            "callsign": row["callsign"],
            "owner": row["owner"],
            "operator": row["operator"],
            "classification_society": row["classification_society"],
            "year_built": row["year_built"],
            "gross_tonnage": float(row["gross_tonnage"]) if row["gross_tonnage"] else None,
            "dwt_estimate": float(row["dwt_estimate"]) if row["dwt_estimate"] else None,
            "length_m": float(row["length_m"]) if row["length_m"] else None,
            "beam_m": float(row["beam_m"]) if row["beam_m"] else None,
            "max_draught": float(row["max_draught"]) if row["max_draught"] else None,
            "flag_country": row["flag_country"],
            "vessel_type": row["vessel_type"],
        }
    }


@router.get("/{mmsi}/trail")
async def get_vessel_trail(
    mmsi: int,
    hours: int = Query(24, le=168),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get vessel trail (position history) for map animation.

    Returns positions sorted chronologically (oldest first).
    Max 168 hours (7 days). Capped at 1000 points.
    """
    result = await db.execute(
        text("""
            SELECT mmsi, latitude, longitude, speed_knots, course, time
            FROM vessel_positions
            WHERE mmsi = :mmsi AND time > NOW() - make_interval(hours => :hours)
            ORDER BY time ASC
            LIMIT 1000
        """),
        {"mmsi": mmsi, "hours": hours},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "mmsi": row["mmsi"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
                "course": float(row["course"]) if row["course"] else None,
                "time": row["time"].isoformat(),
            }
            for row in rows
        ]
    }
