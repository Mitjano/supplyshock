"""Webhook management endpoints — /api/v1/webhooks/*

- POST /webhooks       — register a new webhook
- GET  /webhooks       — list user's webhooks
- DELETE /webhooks/{id} — delete a webhook

Max 5 webhooks per user.
"""

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import _get_user_plan
from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

VALID_EVENTS = {"alert.created", "voyage.started", "voyage.arrived", "price.anomaly"}
MAX_WEBHOOKS_PER_USER = 5
WEBHOOK_PLANS = {"pro", "business", "enterprise"}


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[str]
    secret: str | None = None


def _require_webhook_plan(user: dict[str, Any]) -> None:
    plan = _get_user_plan(user)
    if plan not in WEBHOOK_PLANS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Webhooks require a Pro plan or higher",
                "code": "PLAN_REQUIRED",
                "required_plan": "pro",
                "current_plan": plan,
            },
        )


@router.post("")
async def create_webhook(
    body: WebhookCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook. Max 5 per user."""
    user_id = await resolve_user_id(user, db)
    _require_webhook_plan(user)

    # Validate events
    invalid = set(body.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid events: {', '.join(sorted(invalid))}. "
                   f"Valid: {', '.join(sorted(VALID_EVENTS))}",
        )
    if not body.events:
        raise HTTPException(status_code=400, detail="At least one event is required")

    # Check webhook count
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM user_webhooks WHERE user_id = :uid"),
        {"uid": user_id},
    )
    count = count_result.scalar()
    if count >= MAX_WEBHOOKS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_WEBHOOKS_PER_USER} webhooks per user",
        )

    # Generate secret if not provided
    webhook_secret = body.secret or secrets.token_hex(32)

    await db.execute(
        text("""
            INSERT INTO user_webhooks (user_id, url, events, secret)
            VALUES (:uid, :url, :events, :secret)
        """),
        {
            "uid": user_id,
            "url": str(body.url),
            "events": ",".join(body.events),
            "secret": webhook_secret,
        },
    )
    await db.commit()

    return {
        "data": {
            "url": str(body.url),
            "events": body.events,
            "secret": webhook_secret,
        },
        "message": "Webhook registered successfully",
    }


@router.get("")
async def list_webhooks(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the current user."""
    user_id = await resolve_user_id(user, db)
    _require_webhook_plan(user)

    result = await db.execute(
        text("""
            SELECT id, url, events, created_at
            FROM user_webhooks
            WHERE user_id = :uid
            ORDER BY created_at DESC
        """),
        {"uid": user_id},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "url": row["url"],
                "events": row["events"].split(",") if row["events"] else [],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ],
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook by ID."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            DELETE FROM user_webhooks
            WHERE id = :wid AND user_id = :uid
            RETURNING id
        """),
        {"wid": webhook_id, "uid": user_id},
    )
    deleted = result.scalar()
    await db.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {"message": "Webhook deleted"}
