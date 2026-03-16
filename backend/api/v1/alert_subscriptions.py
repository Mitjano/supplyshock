"""Alert subscription endpoints — /api/v1/alert-subscriptions/*

- GET    /alert-subscriptions       — list user's subscriptions
- POST   /alert-subscriptions       — create subscription
- DELETE /alert-subscriptions/{id}   — delete subscription
"""

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/alert-subscriptions", tags=["Alerts"])

# Internal/private IP ranges that must be blocked for SSRF protection
_BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

_BLOCKED_HOSTNAMES = {"localhost", "0.0.0.0"}


def _validate_webhook_url(url: str) -> str:
    """Validate webhook URL: must be HTTPS and not target internal networks."""
    if not url.startswith("https://"):
        raise ValueError("webhook_url must use HTTPS")

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError("webhook_url cannot target localhost or internal hosts")

    # Check if hostname is an IP address in a blocked range
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_IP_RANGES:
            if addr in network:
                raise ValueError("webhook_url cannot target internal/private IP ranges")
    except ValueError as e:
        if "internal" in str(e) or "localhost" in str(e):
            raise
        # hostname is not an IP — that's fine, it's a domain name
        pass

    return url


class CreateSubscription(BaseModel):
    commodity: str | None = None
    alert_type: str | None = None
    min_severity: str = "warning"
    notify_email: bool = True
    notify_webhook: bool = False
    webhook_url: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_webhook_url(v)
        return v


@router.get("")
async def list_subscriptions(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
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
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
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
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
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
