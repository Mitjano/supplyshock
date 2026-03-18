"""Report endpoints — /api/v1/reports/*

CRUD for generated reports (PDF).
- POST   /reports              — generate a new report
- GET    /reports              — list user's reports
- GET    /reports/{id}         — report detail + download URL
- POST   /reports/{id}/share   — create a shareable link
- GET    /reports/shared/{token} — public access via share link (no auth)
- DELETE /reports/{id}         — delete report
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    simulation_id: str | None = Field(None, description="Link to a completed simulation")
    report_type: str = Field("market_overview", description="e.g. market_overview, disruption_analysis, trade_flow")
    date_from: str | None = Field(None, description="Start date filter (YYYY-MM-DD)")
    date_to: str | None = Field(None, description="End date filter (YYYY-MM-DD)")


class ShareRequest(BaseModel):
    expires_hours: int = Field(72, ge=1, le=720, description="Hours until share link expires")


@router.post("")
async def create_report(
    body: ReportCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new report. Queues PDF generation."""
    user_id = await resolve_user_id(user, db)
    plan = user.get("_db_plan", "free")

    # Plan check: free = 3, pro = 20, business/enterprise = unlimited
    if plan == "free":
        count_result = await db.execute(
            text("SELECT COUNT(*) FROM reports WHERE user_id = :uid"),
            {"uid": user_id},
        )
        count = count_result.scalar()
        if count >= 3:
            raise HTTPException(
                status_code=402,
                detail={"error": "Free plan limited to 3 reports", "code": "PLAN_LIMIT"},
            )

    # If linked to simulation, verify ownership and completion
    params: dict[str, Any] = {
        "uid": user_id,
        "title": body.title,
        "sim_id": None,
    }
    if body.simulation_id:
        sim_result = await db.execute(
            text("SELECT id, status FROM simulations WHERE id = :sid AND user_id = :uid"),
            {"sid": body.simulation_id, "uid": user_id},
        )
        sim = sim_result.mappings().first()
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")
        if sim["status"] != "completed":
            raise HTTPException(status_code=400, detail="Simulation must be completed to generate report")
        params["sim_id"] = body.simulation_id

    result = await db.execute(
        text("""
            INSERT INTO reports (user_id, simulation_id, title, status)
            VALUES (:uid, :sim_id, :title, 'generating')
            RETURNING id, status, created_at
        """),
        params,
    )
    await db.commit()
    row = result.mappings().first()

    # Queue PDF generation task
    try:
        from simulation.tasks import celery_app
        celery_app.send_task(
            "generate_report",
            args=[str(row["id"])],
            queue="analytics",
        )
    except Exception:
        pass  # Celery not running in dev

    return {
        "id": str(row["id"]),
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    }


@router.get("")
async def list_reports(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List user's reports (newest first)."""
    user_id = await resolve_user_id(user, db)

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM reports WHERE user_id = :uid"),
        {"uid": user_id},
    )
    total = count_result.scalar()

    result = await db.execute(
        text("""
            SELECT r.id, r.title, r.status, r.pdf_url, r.page_count,
                   r.file_size_bytes, r.simulation_id, r.share_token,
                   r.share_expires_at, r.created_at
            FROM reports r
            WHERE r.user_id = :uid
            ORDER BY r.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"uid": user_id, "limit": limit, "offset": offset},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "status": r["status"],
                "pdf_url": r["pdf_url"],
                "page_count": r["page_count"],
                "file_size_bytes": r["file_size_bytes"],
                "simulation_id": str(r["simulation_id"]) if r["simulation_id"] else None,
                "has_share_link": r["share_token"] is not None,
                "share_expires_at": r["share_expires_at"].isoformat() if r["share_expires_at"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/shared/{token}")
async def get_shared_report(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public access to a shared report via token. No authentication required."""
    result = await db.execute(
        text("""
            SELECT r.id, r.title, r.status, r.pdf_url, r.page_count,
                   r.file_size_bytes, r.share_expires_at, r.created_at
            FROM reports r
            WHERE r.share_token = :token
        """),
        {"token": token},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Shared report not found or link has expired")

    # Check expiry
    if row["share_expires_at"] and row["share_expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")

    if row["status"] != "ready":
        raise HTTPException(status_code=202, detail="Report is still being generated")

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "status": row["status"],
        "pdf_url": row["pdf_url"],
        "page_count": row["page_count"],
        "file_size_bytes": row["file_size_bytes"],
        "expires_at": row["share_expires_at"].isoformat() if row["share_expires_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get report detail with download URL."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, title, status, pdf_url, page_count, file_size_bytes,
                   simulation_id, share_token, share_expires_at, created_at, updated_at
            FROM reports
            WHERE id = :rid AND user_id = :uid
        """),
        {"rid": report_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "status": row["status"],
        "pdf_url": row["pdf_url"],
        "page_count": row["page_count"],
        "file_size_bytes": row["file_size_bytes"],
        "simulation_id": str(row["simulation_id"]) if row["simulation_id"] else None,
        "share_token": row["share_token"],
        "share_expires_at": row["share_expires_at"].isoformat() if row["share_expires_at"] else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@router.post("/{report_id}/share")
async def create_share_link(
    report_id: str,
    body: ShareRequest | None = None,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Create or refresh a shareable link for a report."""
    user_id = await resolve_user_id(user, db)

    # Verify ownership
    result = await db.execute(
        text("SELECT id, status FROM reports WHERE id = :rid AND user_id = :uid"),
        {"rid": report_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    if row["status"] != "ready":
        raise HTTPException(status_code=400, detail="Report must be ready to share")

    token = secrets.token_urlsafe(32)
    expires_hours = body.expires_hours if body else 72
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    await db.execute(
        text("""
            UPDATE reports
            SET share_token = :token, share_expires_at = :expires, updated_at = NOW()
            WHERE id = :rid
        """),
        {"token": token, "expires": expires_at, "rid": report_id},
    )
    await db.commit()

    return {
        "share_token": token,
        "share_url": f"/reports/shared/{token}",
        "expires_at": expires_at.isoformat(),
    }


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Delete a report."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("SELECT id FROM reports WHERE id = :rid AND user_id = :uid"),
        {"rid": report_id, "uid": user_id},
    )
    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="Report not found")

    await db.execute(
        text("DELETE FROM reports WHERE id = :rid"),
        {"rid": report_id},
    )
    await db.commit()

    return {"status": "deleted"}
