"""Data export endpoints — /api/v1/export/*

- GET /export/vessels   — streaming CSV of vessel positions
- GET /export/voyages   — CSV/XLSX of voyages
- GET /export/prices    — CSV of historical prices

All endpoints require Pro+ plan.
"""

import csv
import io
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import _get_user_plan
from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/export", tags=["Export"])

# Plans that can access export
EXPORT_PLANS = {"pro", "business", "enterprise"}


def _require_export_plan(user: dict[str, Any]) -> None:
    """Raise 403 if user plan does not include export access."""
    plan = _get_user_plan(user)
    if plan not in EXPORT_PLANS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Data export requires a Pro plan or higher",
                "code": "PLAN_REQUIRED",
                "required_plan": "pro",
                "current_plan": plan,
            },
        )


def _csv_streaming_response(rows, columns: list[str], filename: str):
    """Build a StreamingResponse that yields CSV rows."""

    def _generate():
        buf = io.StringIO()
        writer = csv.writer(buf)

        # Header
        writer.writerow(columns)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for row in rows:
            writer.writerow([row[col] for col in columns])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(rows, columns: list[str], filename: str):
    """Build an XLSX file response using openpyxl (optional dependency)."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="XLSX export is not available — openpyxl not installed. Use format=csv instead.",
        )

    wb = Workbook()
    ws = wb.active
    ws.append(columns)
    for row in rows:
        ws.append([row[col] for col in columns])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Vessels ──────────────────────────────────────────────────────────────────

@router.get("/vessels")
async def export_vessels(
    format: str = Query("csv", description="csv"),
    bbox: str | None = Query(None, description="lat1,lon1,lat2,lon2 bounding box"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Export vessel positions as streaming CSV."""
    await resolve_user_id(user, db)
    _require_export_plan(user)

    conditions = []
    params: dict[str, Any] = {}

    if bbox:
        parts = [p.strip() for p in bbox.split(",")]
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail="bbox must be lat1,lon1,lat2,lon2")
        lat1, lon1, lat2, lon2 = (float(p) for p in parts)
        conditions.append("vp.latitude BETWEEN :lat1 AND :lat2")
        conditions.append("vp.longitude BETWEEN :lon1 AND :lon2")
        params.update(lat1=min(lat1, lat2), lat2=max(lat1, lat2),
                      lon1=min(lon1, lon2), lon2=max(lon1, lon2))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT vp.mmsi, vp.imo, vp.vessel_name, vp.vessel_type,
                   vp.latitude, vp.longitude, vp.speed, vp.heading,
                   vp.nav_status, vp.timestamp
            FROM vessel_positions vp
            {where}
            ORDER BY vp.timestamp DESC
            LIMIT 50000
        """),
        params,
    )
    rows = result.mappings().all()

    columns = ["mmsi", "imo", "vessel_name", "vessel_type",
               "latitude", "longitude", "speed", "heading",
               "nav_status", "timestamp"]

    return _csv_streaming_response(rows, columns, "supplyshock_vessels.csv")


# ── Voyages ──────────────────────────────────────────────────────────────────

@router.get("/voyages")
async def export_voyages(
    format: str = Query("csv", description="csv or xlsx"),
    commodity: str | None = Query(None, description="Filter by cargo commodity"),
    status: str | None = Query(None, description="underway, arrived, completed"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Export voyages as CSV or XLSX."""
    await resolve_user_id(user, db)
    _require_export_plan(user)

    conditions = []
    params: dict[str, Any] = {}

    if commodity:
        conditions.append("v.cargo_type = :commodity")
        params["commodity"] = commodity
    if status:
        conditions.append("v.status = :status::voyage_status")
        params["status"] = status

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT v.id, v.mmsi, v.imo, v.vessel_name, v.vessel_type,
                   v.cargo_type, v.status, v.laden_status,
                   v.volume_estimate, v.distance_nm,
                   v.departure_time, v.arrival_time,
                   op.name AS origin_port, op.country_code AS origin_country,
                   dp.name AS dest_port, dp.country_code AS dest_country
            FROM voyages v
            LEFT JOIN ports op ON op.id = v.origin_port_id
            LEFT JOIN ports dp ON dp.id = v.dest_port_id
            {where}
            ORDER BY v.departure_time DESC NULLS LAST
            LIMIT 50000
        """),
        params,
    )
    rows = result.mappings().all()

    columns = ["id", "mmsi", "imo", "vessel_name", "vessel_type",
               "cargo_type", "status", "laden_status",
               "volume_estimate", "distance_nm",
               "departure_time", "arrival_time",
               "origin_port", "origin_country", "dest_port", "dest_country"]

    if format == "xlsx":
        return _xlsx_response(rows, columns, "supplyshock_voyages.xlsx")
    return _csv_streaming_response(rows, columns, "supplyshock_voyages.csv")


# ── Prices ───────────────────────────────────────────────────────────────────

@router.get("/prices")
async def export_prices(
    format: str = Query("csv", description="csv or xlsx"),
    commodity: str | None = Query(None, description="Filter by commodity slug"),
    from_date: date | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Export historical commodity prices as CSV or XLSX."""
    await resolve_user_id(user, db)
    _require_export_plan(user)

    conditions = []
    params: dict[str, Any] = {}

    if commodity:
        conditions.append("cp.commodity_slug = :commodity")
        params["commodity"] = commodity
    if from_date:
        conditions.append("cp.price_date >= :from_date")
        params["from_date"] = from_date.isoformat()
    if to_date:
        conditions.append("cp.price_date <= :to_date")
        params["to_date"] = to_date.isoformat()

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT cp.commodity_slug, cp.price_date, cp.price_usd,
                   cp.unit, cp.source, cp.created_at
            FROM commodity_prices cp
            {where}
            ORDER BY cp.price_date DESC
            LIMIT 100000
        """),
        params,
    )
    rows = result.mappings().all()

    columns = ["commodity_slug", "price_date", "price_usd", "unit", "source", "created_at"]

    if format == "xlsx":
        return _xlsx_response(rows, columns, "supplyshock_prices.xlsx")
    return _csv_streaming_response(rows, columns, "supplyshock_prices.csv")
