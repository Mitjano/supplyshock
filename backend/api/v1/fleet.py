"""Fleet analytics endpoints — /api/v1/fleet/*

- GET /fleet             — fleet summary for an owner
- GET /fleet/top         — top owners by DWT, vessel count, etc.
- GET /fleet/{owner}/exposure — commodity and region exposure
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/fleet", tags=["Fleet Analytics"])


@router.get("")
async def get_fleet(
    owner: str = Query(..., description="Fleet owner name (e.g. Maersk, COSCO)"),
    vessel_type: str | None = Query(None, description="Filter by vessel type"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get fleet summary and vessel list for a given owner."""
    conditions = ["LOWER(vsd.owner) = LOWER(:owner)"]
    params: dict[str, Any] = {"owner": owner}

    if vessel_type:
        conditions.append("vsd.vessel_type = :vessel_type")
        params["vessel_type"] = vessel_type

    where = f"WHERE {' AND '.join(conditions)}"

    # Summary stats
    summary_result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) as vessel_count,
                COALESCE(SUM(vsd.dwt), 0) as total_dwt,
                ROUND(AVG(EXTRACT(YEAR FROM NOW()) - vsd.year_built), 1) as avg_age,
                COUNT(DISTINCT vsd.vessel_type) as type_count
            FROM vessel_static_data vsd
            {where}
        """),
        params,
    )
    summary = summary_result.mappings().first()

    if not summary or summary["vessel_count"] == 0:
        raise HTTPException(status_code=404, detail=f"No vessels found for owner '{owner}'")

    # Utilization: vessels with active voyages / total
    util_result = await db.execute(
        text(f"""
            SELECT COUNT(DISTINCT v.mmsi) as active_vessels
            FROM voyages v
            JOIN vessel_static_data vsd ON v.mmsi = vsd.mmsi
            {where}
              AND v.status = 'underway'
        """),
        params,
    )
    util_row = util_result.mappings().first()
    active = util_row["active_vessels"] if util_row else 0
    utilization = round(active / summary["vessel_count"] * 100, 1) if summary["vessel_count"] > 0 else 0

    # Vessel list
    vessels_result = await db.execute(
        text(f"""
            SELECT vsd.mmsi, vsd.imo, vsd.name, vsd.vessel_type, vsd.dwt,
                   vsd.year_built, vsd.flag,
                   EXTRACT(YEAR FROM NOW()) - vsd.year_built as age
            FROM vessel_static_data vsd
            {where}
            ORDER BY vsd.dwt DESC NULLS LAST
            LIMIT 200
        """),
        params,
    )
    vessels = vessels_result.mappings().all()

    return {
        "data": {
            "owner": owner,
            "vessel_count": summary["vessel_count"],
            "total_dwt": float(summary["total_dwt"]),
            "avg_age": float(summary["avg_age"]) if summary["avg_age"] else None,
            "utilization_pct": utilization,
            "vessels": [
                {
                    "mmsi": v["mmsi"],
                    "imo": v["imo"],
                    "name": v["name"],
                    "vessel_type": v["vessel_type"],
                    "dwt": float(v["dwt"]) if v["dwt"] else None,
                    "year_built": v["year_built"],
                    "flag": v["flag"],
                    "age": float(v["age"]) if v["age"] else None,
                }
                for v in vessels
            ],
        },
    }


@router.get("/top")
async def get_top_owners(
    by: str = Query("dwt", description="Rank by: dwt, vessel_count, avg_age"),
    vessel_type: str | None = Query(None, description="Filter by vessel type"),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get top fleet owners ranked by DWT, vessel count, or average age."""
    order_map = {
        "dwt": "total_dwt DESC",
        "vessel_count": "vessel_count DESC",
        "avg_age": "avg_age ASC",
    }
    order_by = order_map.get(by, "total_dwt DESC")

    conditions = ["vsd.owner IS NOT NULL", "vsd.owner != ''"]
    params: dict[str, Any] = {"limit": limit}

    if vessel_type:
        conditions.append("vsd.vessel_type = :vessel_type")
        params["vessel_type"] = vessel_type

    where = f"WHERE {' AND '.join(conditions)}"

    result = await db.execute(
        text(f"""
            SELECT
                vsd.owner,
                COUNT(*) as vessel_count,
                COALESCE(SUM(vsd.dwt), 0) as total_dwt,
                ROUND(AVG(EXTRACT(YEAR FROM NOW()) - vsd.year_built), 1) as avg_age
            FROM vessel_static_data vsd
            {where}
            GROUP BY vsd.owner
            ORDER BY {order_by}
            LIMIT :limit
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "owner": r["owner"],
                "vessel_count": r["vessel_count"],
                "total_dwt": float(r["total_dwt"]),
                "avg_age": float(r["avg_age"]) if r["avg_age"] else None,
            }
            for r in rows
        ],
        "meta": {"ranked_by": by, "vessel_type": vessel_type, "limit": limit},
    }


@router.get("/{owner}/exposure")
async def get_fleet_exposure(
    owner: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get commodity and region exposure breakdown for a fleet owner."""
    params: dict[str, Any] = {"owner": owner}

    # Commodity breakdown from voyages
    commodity_result = await db.execute(
        text("""
            SELECT v.cargo_type as commodity,
                   COUNT(*) as voyage_count,
                   SUM(v.volume_estimate) as total_volume
            FROM voyages v
            JOIN vessel_static_data vsd ON v.mmsi = vsd.mmsi
            WHERE LOWER(vsd.owner) = LOWER(:owner)
              AND v.cargo_type IS NOT NULL
              AND v.departure_time > NOW() - INTERVAL '90 days'
            GROUP BY v.cargo_type
            ORDER BY voyage_count DESC
        """),
        params,
    )
    commodities = commodity_result.mappings().all()

    # Region breakdown from voyage destinations
    region_result = await db.execute(
        text("""
            SELECT p.region,
                   COUNT(*) as voyage_count,
                   COUNT(DISTINCT v.mmsi) as vessel_count
            FROM voyages v
            JOIN vessel_static_data vsd ON v.mmsi = vsd.mmsi
            LEFT JOIN ports p ON v.destination_port_id = p.id
            WHERE LOWER(vsd.owner) = LOWER(:owner)
              AND p.region IS NOT NULL
              AND v.departure_time > NOW() - INTERVAL '90 days'
            GROUP BY p.region
            ORDER BY voyage_count DESC
        """),
        params,
    )
    regions = region_result.mappings().all()

    if not commodities and not regions:
        raise HTTPException(status_code=404, detail=f"No voyage data found for owner '{owner}'")

    return {
        "data": {
            "owner": owner,
            "period": "90d",
            "commodity_exposure": [
                {
                    "commodity": c["commodity"],
                    "voyage_count": c["voyage_count"],
                    "total_volume": float(c["total_volume"]) if c["total_volume"] else None,
                }
                for c in commodities
            ],
            "region_exposure": [
                {
                    "region": r["region"],
                    "voyage_count": r["voyage_count"],
                    "vessel_count": r["vessel_count"],
                }
                for r in regions
            ],
        },
    }
