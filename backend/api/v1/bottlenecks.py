"""Bottleneck endpoints — /api/v1/bottlenecks/*

- GET /bottlenecks                    — list all bottleneck nodes
- GET /bottlenecks/{slug}             — node detail
- GET /bottlenecks/{slug}/status      — live status + history
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/bottlenecks", tags=["Bottlenecks"])


@router.get("")
async def list_bottlenecks(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all bottleneck nodes."""
    result = await db.execute(
        text("""
            SELECT id, slug, name, type, country_code, latitude, longitude,
                   commodities, annual_volume_mt, global_share_pct, baseline_risk,
                   description
            FROM bottleneck_nodes
            ORDER BY baseline_risk DESC, name ASC
        """),
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "slug": row["slug"],
                "name": row["name"],
                "type": row["type"],
                "country_code": row["country_code"],
                "latitude": float(row["latitude"]) if row["latitude"] else None,
                "longitude": float(row["longitude"]) if row["longitude"] else None,
                "commodities": row["commodities"] or [],
                "annual_volume_mt": float(row["annual_volume_mt"]) if row["annual_volume_mt"] else None,
                "global_share_pct": float(row["global_share_pct"]) if row["global_share_pct"] else None,
                "baseline_risk": row["baseline_risk"],
                "description": row["description"],
            }
            for row in rows
        ]
    }


@router.get("/{slug}")
async def get_bottleneck(
    slug: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get bottleneck node detail."""
    result = await db.execute(
        text("""
            SELECT id, slug, name, type, country_code, latitude, longitude,
                   commodities, annual_volume_mt, global_share_pct, baseline_risk,
                   description, wikipedia_url
            FROM bottleneck_nodes
            WHERE slug = :slug
        """),
        {"slug": slug},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail={"error": "Bottleneck not found", "code": "NOT_FOUND"})

    return {
        "data": {
            "id": str(row["id"]),
            "slug": row["slug"],
            "name": row["name"],
            "type": row["type"],
            "country_code": row["country_code"],
            "latitude": float(row["latitude"]) if row["latitude"] else None,
            "longitude": float(row["longitude"]) if row["longitude"] else None,
            "commodities": row["commodities"] or [],
            "annual_volume_mt": float(row["annual_volume_mt"]) if row["annual_volume_mt"] else None,
            "global_share_pct": float(row["global_share_pct"]) if row["global_share_pct"] else None,
            "baseline_risk": row["baseline_risk"],
            "description": row["description"],
            "wikipedia_url": row["wikipedia_url"],
        }
    }


@router.get("/{slug}/status")
async def get_bottleneck_status(
    slug: str,
    history_days: int = Query(7, le=30),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get real-time congestion status for a bottleneck + history."""
    # Verify node exists
    node_result = await db.execute(
        text("SELECT id, name, baseline_risk FROM bottleneck_nodes WHERE slug = :slug"),
        {"slug": slug},
    )
    node = node_result.mappings().first()
    if not node:
        raise HTTPException(status_code=404, detail={"error": "Bottleneck not found", "code": "NOT_FOUND"})

    # Get status history
    result = await db.execute(
        text("""
            SELECT vessel_count, avg_speed_knots, congestion_index, risk_level, time
            FROM chokepoint_status
            WHERE node_id = :node_id
              AND time > NOW() - make_interval(days => :history_days)
            ORDER BY time DESC
        """),
        {"node_id": node["id"], "history_days": history_days},
    )
    rows = result.mappings().all()

    current = rows[0] if rows else None

    return {
        "data": {
            "slug": slug,
            "name": node["name"],
            "current": {
                "vessel_count": current["vessel_count"] if current else 0,
                "avg_speed_knots": float(current["avg_speed_knots"]) if current and current["avg_speed_knots"] else None,
                "congestion_index": float(current["congestion_index"]) if current and current["congestion_index"] else None,
                "risk_level": current["risk_level"] if current else "unknown",
                "time": current["time"].isoformat() if current else None,
            },
            "history": [
                {
                    "vessel_count": row["vessel_count"],
                    "congestion_index": float(row["congestion_index"]) if row["congestion_index"] else None,
                    "risk_level": row["risk_level"],
                    "time": row["time"].isoformat(),
                }
                for row in rows
            ],
        }
    }
