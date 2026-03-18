"""Notification channel management — /api/v1/notifications/*

- POST   /notifications/channels       — create a notification channel
- GET    /notifications/channels       — list user's channels
- DELETE /notifications/channels/{id}  — delete a channel
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/notifications", tags=["Notifications"])

VALID_CHANNEL_TYPES = {"slack", "telegram", "discord"}
VALID_EVENTS = {"alert.created", "voyage.started", "voyage.arrived", "price.anomaly"}
MAX_CHANNELS_PER_USER = 10


class ChannelCreate(BaseModel):
    channel_type: str
    webhook_url: str | None = None
    bot_token: str | None = None
    chat_id: str | None = None
    events: list[str]


@router.post("/channels")
async def create_channel(
    body: ChannelCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Register a new notification channel."""
    user_id = await resolve_user_id(user, db)

    if body.channel_type not in VALID_CHANNEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel_type. Valid: {', '.join(sorted(VALID_CHANNEL_TYPES))}",
        )

    invalid = set(body.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid events: {', '.join(sorted(invalid))}. "
                   f"Valid: {', '.join(sorted(VALID_EVENTS))}",
        )
    if not body.events:
        raise HTTPException(status_code=400, detail="At least one event is required")

    # Validate required fields per channel type
    if body.channel_type in ("slack", "discord") and not body.webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required for Slack/Discord")
    if body.channel_type == "telegram" and (not body.bot_token or not body.chat_id):
        raise HTTPException(status_code=400, detail="bot_token and chat_id are required for Telegram")

    # Check channel count
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM notification_channels WHERE user_id = :uid"),
        {"uid": user_id},
    )
    count = count_result.scalar()
    if count >= MAX_CHANNELS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_CHANNELS_PER_USER} notification channels per user",
        )

    result = await db.execute(
        text("""
            INSERT INTO notification_channels
                (user_id, channel_type, webhook_url, bot_token, chat_id, events, enabled)
            VALUES (:uid, :ctype, :wurl, :btoken, :cid, :events, true)
            RETURNING id
        """),
        {
            "uid": user_id,
            "ctype": body.channel_type,
            "wurl": body.webhook_url,
            "btoken": body.bot_token,
            "cid": body.chat_id,
            "events": ",".join(body.events),
        },
    )
    channel_id = result.scalar()
    await db.commit()

    return {
        "data": {
            "id": str(channel_id),
            "channel_type": body.channel_type,
            "events": body.events,
        },
        "message": "Notification channel created successfully",
    }


@router.get("/channels")
async def list_channels(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all notification channels for the current user."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, channel_type, webhook_url, chat_id, events, enabled, created_at
            FROM notification_channels
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
                "channel_type": row["channel_type"],
                "webhook_url": row["webhook_url"],
                "chat_id": row["chat_id"],
                "events": row["events"].split(",") if row["events"] else [],
                "enabled": row["enabled"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ],
    }


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification channel by ID."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            DELETE FROM notification_channels
            WHERE id = :cid AND user_id = :uid
            RETURNING id
        """),
        {"cid": channel_id, "uid": user_id},
    )
    deleted = result.scalar()
    await db.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Notification channel not found")

    return {"message": "Notification channel deleted"}
