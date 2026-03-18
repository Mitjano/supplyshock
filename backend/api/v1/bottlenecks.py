"""Bottleneck endpoints — /api/v1/bottlenecks/*

- GET /bottlenecks             — list all bottleneck nodes
- GET /bottlenecks/{slug}      — node detail + status history
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/bottlenecks", tags=["Bottlenecks"])


@router.get("")
async def list_bottlenecks(
    commodity: str | None = Query(None, description="Filter by commodity"),
    type: str | None = Query(None, description="Filter: port, strait, pipeline, rail"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all bottleneck nodes with latest congestion status."""
    conditions = []
    params: dict[str, Any] = {}

    if commodity:
        conditions.append(":commodity = ANY(bn.commodities)")
        params["commodity"] = commodity
    if type:
        conditions.append("bn.type = :type")
        params["type"] = type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT bn.id, bn.slug, bn.name, bn.type, bn.country_code,
                   bn.latitude, bn.longitude, bn.commodities,
                   bn.annual_volume_mt, bn.global_share_pct, bn.baseline_risk,
                   bn.description,
                   cs.vessel_count, cs.avg_speed_knots, cs.congestion_index,
                   cs.risk_level, cs.time as status_time
            FROM bottleneck_nodes bn
            LEFT JOIN LATERAL (
                SELECT vessel_count, avg_speed_knots, congestion_index, risk_level, time
                FROM chokepoint_status
                WHERE node_id = bn.id
                ORDER BY time DESC
                LIMIT 1
            ) cs ON TRUE
            {where}
            ORDER BY bn.global_share_pct DESC NULLS LAST
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "slug": r["slug"],
                "name": r["name"],
                "type": r["type"],
                "country_code": r["country_code"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "commodities": r["commodities"],
                "annual_volume_mt": float(r["annual_volume_mt"]) if r["annual_volume_mt"] else None,
                "global_share_pct": float(r["global_share_pct"]) if r["global_share_pct"] else None,
                "baseline_risk": r["baseline_risk"],
                "description": r["description"],
                "status": {
                    "vessel_count": r["vessel_count"],
                    "avg_speed_knots": float(r["avg_speed_knots"]) if r["avg_speed_knots"] else None,
                    "congestion_index": float(r["congestion_index"]) if r["congestion_index"] else None,
                    "risk_level": r["risk_level"] or "normal",
                    "updated_at": r["status_time"].isoformat() if r["status_time"] else None,
                } if r["vessel_count"] is not None else None,
            }
            for r in rows
        ]
    }


@router.get("/{slug}")
async def get_bottleneck(
    slug: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get bottleneck node detail with 7-day status history and recent alerts."""
    result = await db.execute(
        text("""
            SELECT id, slug, name, type, country_code, latitude, longitude,
                   commodities, annual_volume_mt, global_share_pct, baseline_risk,
                   description, wikipedia_url
            FROM bottleneck_nodes WHERE slug = :slug
        """),
        {"slug": slug},
    )
    node = result.mappings().first()
    if not node:
        raise HTTPException(status_code=404, detail="Bottleneck node not found")

    node_id = str(node["id"])

    status_result = await db.execute(
        text("""
            SELECT vessel_count, avg_speed_knots, congestion_index, risk_level, time
            FROM chokepoint_status
            WHERE node_id = :node_id AND time > NOW() - INTERVAL '7 days'
            ORDER BY time ASC
        """),
        {"node_id": node_id},
    )
    status_rows = status_result.mappings().all()

    alert_result = await db.execute(
        text("""
            SELECT id, time, type, severity, title, body, source_url
            FROM alert_events
            WHERE metadata->>'node_slug' = :slug
              AND time > NOW() - INTERVAL '30 days'
            ORDER BY time DESC
            LIMIT 10
        """),
        {"slug": slug},
    )
    alert_rows = alert_result.mappings().all()

    return {
        "node": {
            "id": node_id,
            "slug": node["slug"],
            "name": node["name"],
            "type": node["type"],
            "country_code": node["country_code"],
            "latitude": node["latitude"],
            "longitude": node["longitude"],
            "commodities": node["commodities"],
            "annual_volume_mt": float(node["annual_volume_mt"]) if node["annual_volume_mt"] else None,
            "global_share_pct": float(node["global_share_pct"]) if node["global_share_pct"] else None,
            "baseline_risk": node["baseline_risk"],
            "description": node["description"],
            "wikipedia_url": node["wikipedia_url"],
        },
        "status_history": [
            {
                "vessel_count": r["vessel_count"],
                "avg_speed_knots": float(r["avg_speed_knots"]) if r["avg_speed_knots"] else None,
                "congestion_index": float(r["congestion_index"]) if r["congestion_index"] else None,
                "risk_level": r["risk_level"],
                "time": r["time"].isoformat(),
            }
            for r in status_rows
        ],
        "recent_alerts": [
            {
                "id": str(r["id"]),
                "time": r["time"].isoformat(),
                "type": r["type"],
                "severity": r["severity"],
                "title": r["title"],
                "body": r["body"],
                "source_url": r["source_url"],
            }
            for r in alert_rows
        ],
    }
