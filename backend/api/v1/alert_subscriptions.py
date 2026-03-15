"""Alert subscription endpoints — /api/v1/alert-subscriptions/*

- GET    /alert-subscriptions       — list user's subscriptions
- POST   /alert-subscriptions       — create subscription
- DELETE /alert-subscriptions/{id}   — delete subscription
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

router = APIRouter(prefix="/alert-subscriptions", tags=["Alerts"])


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class CreateSubscription(BaseModel):
    commodity: str | None = None
    alert_type: str | None = None
    min_severity: str = "warning"
    notify_email: bool = True
    notify_webhook: bool = False
    webhook_url: str | None = None


@router.get("")
async def list_subscriptions(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """List current user's alert subscriptions."""
    clerk_id = user.get("sub")

    result = await db.execute(
        text("""
            SELECT s.id, s.commodity, s.alert_type, s.min_severity,
                   s.notify_email, s.notify_webhook, s.webhook_url, s.created_at
            FROM user_alert_subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE u.clerk_user_id = :clerk_id
            ORDER BY s.created_at DESC
        """),
        {"clerk_id": clerk_id},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "commodity": row["commodity"],
                "alert_type": row["alert_type"],
                "min_severity": row["min_severity"],
                "notify_email": row["notify_email"],
                "notify_webhook": row["notify_webhook"],
                "webhook_url": row["webhook_url"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }


@router.post("", status_code=201)
async def create_subscription(
    body: CreateSubscription,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Create an alert subscription."""
    clerk_id = user.get("sub")

    # Get user ID
    user_result = await db.execute(
        text("SELECT id FROM users WHERE clerk_user_id = :clerk_id"),
        {"clerk_id": clerk_id},
    )
    user_row = user_result.mappings().first()
    if not user_row:
        raise HTTPException(status_code=404, detail={"error": "User not found", "code": "USER_NOT_FOUND"})

    result = await db.execute(
        text("""
            INSERT INTO user_alert_subscriptions
                (user_id, commodity, alert_type, min_severity,
                 notify_email, notify_webhook, webhook_url)
            VALUES (:user_id, :commodity, :alert_type, :min_severity,
                    :notify_email, :notify_webhook, :webhook_url)
            RETURNING id, created_at
        """),
        {
            "user_id": user_row["id"],
            "commodity": body.commodity,
            "alert_type": body.alert_type,
            "min_severity": body.min_severity,
            "notify_email": body.notify_email,
            "notify_webhook": body.notify_webhook,
            "webhook_url": body.webhook_url,
        },
    )
    await db.commit()
    row = result.mappings().first()

    return {
        "data": {
            "id": str(row["id"]),
            "commodity": body.commodity,
            "alert_type": body.alert_type,
            "min_severity": body.min_severity,
            "created_at": row["created_at"].isoformat(),
        }
    }


@router.delete("/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Delete an alert subscription (must belong to current user)."""
    clerk_id = user.get("sub")

    result = await db.execute(
        text("""
            DELETE FROM user_alert_subscriptions s
            USING users u
            WHERE s.user_id = u.id
              AND u.clerk_user_id = :clerk_id
              AND s.id = :sub_id
            RETURNING s.id
        """),
        {"clerk_id": clerk_id, "sub_id": subscription_id},
    )
    await db.commit()

    if not result.first():
        raise HTTPException(status_code=404, detail={"error": "Subscription not found", "code": "NOT_FOUND"})
