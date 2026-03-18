"""Alert subscription endpoints — /api/v1/alert-subscriptions/*

- GET    /alert-subscriptions       — list user's subscriptions
- POST   /alert-subscriptions       — create subscription
- DELETE /alert-subscriptions/{id}  — delete subscription
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/alert-subscriptions", tags=["Alert Subscriptions"])


class SubscriptionCreate(BaseModel):
    commodity: str | None = Field(None, description="NULL = all commodities")
    alert_type: str | None = Field(None, description="NULL = all alert types")
    min_severity: str = Field("warning", description="Minimum severity: info, warning, critical")
    notify_email: bool = Field(True)
    notify_webhook: bool = Field(False)
    webhook_url: str | None = Field(None)


@router.get("")
async def list_subscriptions(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List user's alert subscriptions."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, commodity, alert_type, min_severity,
                   notify_email, notify_webhook, webhook_url, created_at
            FROM user_alert_subscriptions
            WHERE user_id = :uid
            ORDER BY created_at DESC
        """),
        {"uid": user_id},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "commodity": r["commodity"],
                "alert_type": r["alert_type"],
                "min_severity": r["min_severity"],
                "notify_email": r["notify_email"],
                "notify_webhook": r["notify_webhook"],
                "webhook_url": r["webhook_url"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.post("", status_code=201)
async def create_subscription(
    body: SubscriptionCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert subscription."""
    user_id = await resolve_user_id(user, db)

    if body.min_severity not in ("info", "warning", "critical"):
        raise HTTPException(status_code=400, detail="min_severity must be info, warning, or critical")

    if body.notify_webhook and not body.webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url required when notify_webhook is true")

    # Max 20 subscriptions per user
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM user_alert_subscriptions WHERE user_id = :uid"),
        {"uid": user_id},
    )
    if count_result.scalar() >= 20:
        raise HTTPException(status_code=400, detail="Maximum 20 alert subscriptions per user")

    try:
        result = await db.execute(
            text("""
                INSERT INTO user_alert_subscriptions
                    (user_id, commodity, alert_type, min_severity,
                     notify_email, notify_webhook, webhook_url)
                VALUES (:uid, :commodity, :alert_type, :min_severity,
                        :notify_email, :notify_webhook, :webhook_url)
                RETURNING id, created_at
            """),
            {
                "uid": user_id,
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
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}
    except Exception as e:
        await db.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Subscription with this commodity/alert_type combination already exists",
            )
        raise


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert subscription."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            DELETE FROM user_alert_subscriptions
            WHERE id = :sid AND user_id = :uid
            RETURNING id
        """),
        {"sid": subscription_id, "uid": user_id},
    )
    await db.commit()

    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {"status": "deleted"}
