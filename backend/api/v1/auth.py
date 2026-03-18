"""Auth endpoints — /api/v1/auth/*

- GET    /auth/me   — return current user from local DB
- POST   /auth/sync — create or update user in local DB from Clerk JWT
- DELETE /auth/me   — GDPR account deletion (cascade all user data)
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me")
async def get_me(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's profile from local DB.

    Requires valid Clerk JWT. Returns 404 if user hasn't synced yet.
    """
    clerk_user_id = user.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail={"error": "Invalid token payload", "code": "INVALID_TOKEN"})

    result = await db.execute(
        text("""
            SELECT id, clerk_user_id, email, name, avatar_url, plan,
                   plan_expires_at, created_at, updated_at, last_seen_at,
                   onboarding_completed_steps
            FROM users WHERE clerk_user_id = :clerk_id
        """),
        {"clerk_id": clerk_user_id},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "User not found. Call POST /auth/sync first.", "code": "USER_NOT_FOUND"},
        )

    # Update last_seen_at
    await db.execute(
        text("UPDATE users SET last_seen_at = NOW() WHERE clerk_user_id = :clerk_id"),
        {"clerk_id": clerk_user_id},
    )
    await db.commit()

    return {
        "data": {
            "id": str(row["id"]),
            "clerk_user_id": row["clerk_user_id"],
            "email": row["email"],
            "name": row["name"],
            "avatar_url": row["avatar_url"],
            "plan": row["plan"],
            "plan_expires_at": row["plan_expires_at"].isoformat() if row["plan_expires_at"] else None,
            "onboarding_completed_steps": row["onboarding_completed_steps"],
            "created_at": row["created_at"].isoformat(),
        }
    }


@router.post("/sync", status_code=200)
async def sync_user(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user in local DB from Clerk JWT payload.

    Called by frontend after login. Upserts based on clerk_user_id.
    """
    clerk_user_id = user.get("sub")
    email = user.get("email", user.get("email_addresses", [{}])[0].get("email_address", "")) if isinstance(user.get("email_addresses"), list) else user.get("email", "")
    name = user.get("name", user.get("first_name", ""))
    avatar_url = user.get("image_url", user.get("profile_image_url"))

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail={"error": "Invalid token payload", "code": "INVALID_TOKEN"})

    # Upsert: insert if new, update if existing
    result = await db.execute(
        text("""
            INSERT INTO users (clerk_user_id, email, name, avatar_url, last_seen_at)
            VALUES (:clerk_id, :email, :name, :avatar_url, NOW())
            ON CONFLICT (clerk_user_id) DO UPDATE SET
                email = EXCLUDED.email,
                name = COALESCE(EXCLUDED.name, users.name),
                avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                last_seen_at = NOW(),
                updated_at = NOW()
            RETURNING id, clerk_user_id, email, name, plan, created_at
        """),
        {
            "clerk_id": clerk_user_id,
            "email": email,
            "name": name,
            "avatar_url": avatar_url,
        },
    )
    await db.commit()
    row = result.mappings().first()

    return {
        "data": {
            "id": str(row["id"]),
            "clerk_user_id": row["clerk_user_id"],
            "email": row["email"],
            "name": row["name"],
            "plan": row["plan"],
            "created_at": row["created_at"].isoformat(),
        }
    }


@router.delete("/me")
async def delete_account(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """GDPR account deletion — permanently removes user and all associated data.

    Cascades to: subscriptions, api_keys, simulations, reports, alert_subscriptions.
    Audit log entries are preserved with user_id set to NULL.

    Also cancels any active Stripe subscription and attempts to delete the Clerk user.
    """
    clerk_user_id = user.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail={"error": "Invalid token", "code": "INVALID_TOKEN"})

    # Fetch user from DB
    result = await db.execute(
        text("SELECT id, email, stripe_customer_id FROM users WHERE clerk_user_id = :cid"),
        {"cid": clerk_user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "User not found", "code": "USER_NOT_FOUND"})

    user_id = str(row["id"])
    user_email = row["email"]
    stripe_customer_id = row["stripe_customer_id"]

    # 1. Cancel active Stripe subscriptions (if any)
    if stripe_customer_id:
        try:
            import stripe
            from config import settings
            stripe.api_key = settings.STRIPE_SECRET_KEY
            subscriptions_list = stripe.Subscription.list(customer=stripe_customer_id, status="active")
            for sub in subscriptions_list.data:
                stripe.Subscription.cancel(sub.id)
            logger.info("Cancelled Stripe subscriptions for user %s", user_id)
        except Exception as e:
            logger.warning("Failed to cancel Stripe subscriptions for user %s: %s", user_id, e)

    # 2. Revoke any running Celery tasks (simulations)
    try:
        running_result = await db.execute(
            text("""
                SELECT celery_task_id FROM simulations
                WHERE user_id = :uid AND status IN ('queued', 'running') AND celery_task_id IS NOT NULL
            """),
            {"uid": user_id},
        )
        task_rows = running_result.mappings().all()
        if task_rows:
            from simulation.tasks import celery_app
            for t in task_rows:
                celery_app.control.revoke(t["celery_task_id"], terminate=True)
    except Exception as e:
        logger.warning("Failed to revoke Celery tasks for user %s: %s", user_id, e)

    # 3. Write audit log entry (before deletion — user_id will become NULL via ON DELETE SET NULL)
    await db.execute(
        text("""
            INSERT INTO audit_log (user_id, action, resource, ip_address, user_agent, metadata)
            VALUES (:uid, 'account.delete', 'user', :ip, :ua, :meta)
        """),
        {
            "uid": user_id,
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent"),
            "meta": json.dumps({"email": user_email, "clerk_user_id": clerk_user_id}),
        },
    )

    # 4. Delete user — CASCADE removes subscriptions, api_keys, simulations, reports, alert_subscriptions
    await db.execute(
        text("DELETE FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    await db.commit()

    # 5. Delete user from Clerk (best-effort, non-blocking)
    try:
        from config import settings
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"https://api.clerk.com/v1/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            )
            if resp.status_code == 200:
                logger.info("Deleted Clerk user %s", clerk_user_id)
            else:
                logger.warning("Clerk user deletion returned %s: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Failed to delete Clerk user %s: %s", clerk_user_id, e)

    return {"status": "deleted", "message": "Account and all associated data have been permanently removed."}
