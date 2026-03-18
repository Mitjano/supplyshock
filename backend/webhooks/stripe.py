"""Stripe webhook handler — /webhooks/stripe

Verifies Stripe signature, processes:
- checkout.session.completed  → upgrade plan
- invoice.payment_failed      → warning email, 3 failures → downgrade
- customer.subscription.deleted → immediate downgrade
"""

import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICE_MAP: dict[str, str] = {
    # price_id → plan name  (set real IDs in production)
    "price_pro_monthly": "pro",
    "price_business_monthly": "business",
    "price_enterprise_monthly": "enterprise",
}


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


def _resolve_plan(session_or_sub: dict) -> str:
    """Extract plan name from Stripe line items / subscription."""
    items = session_or_sub.get("items", {}).get("data", [])
    if not items:
        # checkout session — check metadata
        metadata = session_or_sub.get("metadata", {})
        return metadata.get("plan", "pro")

    price_id = items[0].get("price", {}).get("id", "")
    return PLAN_PRICE_MAP.get(price_id, "pro")


async def _update_user_plan(db: AsyncSession, stripe_customer_id: str, plan: str):
    """Update user plan in DB by Stripe customer ID."""
    await db.execute(
        text("""
            UPDATE users SET plan = :plan, updated_at = NOW()
            WHERE stripe_customer_id = :cid
        """),
        {"plan": plan, "cid": stripe_customer_id},
    )
    await db.commit()


async def _get_failure_count(db: AsyncSession, stripe_customer_id: str) -> int:
    """Count consecutive payment failures for a customer."""
    result = await db.execute(
        text("""
            SELECT payment_failure_count FROM users
            WHERE stripe_customer_id = :cid
        """),
        {"cid": stripe_customer_id},
    )
    row = result.mappings().first()
    return row["payment_failure_count"] if row else 0


async def _increment_failure_count(db: AsyncSession, stripe_customer_id: str) -> int:
    """Increment failure counter, return new value."""
    result = await db.execute(
        text("""
            UPDATE users
            SET payment_failure_count = COALESCE(payment_failure_count, 0) + 1,
                updated_at = NOW()
            WHERE stripe_customer_id = :cid
            RETURNING payment_failure_count
        """),
        {"cid": stripe_customer_id},
    )
    await db.commit()
    row = result.mappings().first()
    return row["payment_failure_count"] if row else 1


async def _reset_failure_count(db: AsyncSession, stripe_customer_id: str):
    await db.execute(
        text("""
            UPDATE users SET payment_failure_count = 0, updated_at = NOW()
            WHERE stripe_customer_id = :cid
        """),
        {"cid": stripe_customer_id},
    )
    await db.commit()


async def _get_user_by_customer(db: AsyncSession, stripe_customer_id: str) -> dict | None:
    """Get user name and email by Stripe customer ID."""
    result = await db.execute(
        text("SELECT name, email, plan FROM users WHERE stripe_customer_id = :cid"),
        {"cid": stripe_customer_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    payload = await request.body()

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, detail="Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, detail="Invalid signature")
    except Exception as e:
        logger.error("Stripe webhook error: %s", e)
        raise HTTPException(400, detail="Invalid payload")

    # Idempotency check: skip already-processed events (24h TTL in Redis)
    from main import redis_client

    event_id = event.get("id", "")
    dedup_key = f"stripe_webhook:{event_id}"
    already_processed = await redis_client.set(dedup_key, "1", ex=86400, nx=True)
    if not already_processed:
        # SET NX returned None/False — key already existed, event was processed
        logger.info("Skipping duplicate Stripe event %s", event_id)
        return {"status": "duplicate"}

    # Get DB session manually (not via Depends in webhook)
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "checkout.session.completed":
            customer_id = data.get("customer")
            plan = data.get("metadata", {}).get("plan", "pro")

            # Link Stripe customer to user if not yet linked
            clerk_id = data.get("metadata", {}).get("clerk_user_id")
            if clerk_id and customer_id:
                await db.execute(
                    text("""
                        UPDATE users
                        SET stripe_customer_id = :cid, plan = :plan,
                            payment_failure_count = 0, updated_at = NOW()
                        WHERE clerk_user_id = :clerk_id
                    """),
                    {"cid": customer_id, "plan": plan, "clerk_id": clerk_id},
                )
                await db.commit()
            elif customer_id:
                await _update_user_plan(db, customer_id, plan)
                await _reset_failure_count(db, customer_id)

            logger.info("Plan upgraded to %s for customer %s", plan, customer_id)

            # Send welcome email
            if customer_id:
                user_info = await _get_user_by_customer(db, customer_id)
                if user_info and user_info.get("email"):
                    from emails.resend import send_email
                    await send_email("welcome_pro", user_info["email"], {
                        "name": user_info.get("name") or "there",
                        "plan_name": plan.title(),
                        "app_url": settings.FRONTEND_URL,
                    })

        elif event_type == "invoice.payment_failed":
            customer_id = data.get("customer")
            if customer_id:
                count = await _increment_failure_count(db, customer_id)
                logger.warning(
                    "Payment failed for %s (attempt %d)", customer_id, count
                )

                user_info = await _get_user_by_customer(db, customer_id)

                if count >= 3:
                    await _update_user_plan(db, customer_id, "free")
                    logger.warning("Downgraded %s to free after 3 failures", customer_id)

                    # Send downgrade email
                    if user_info and user_info.get("email"):
                        from emails.resend import send_email
                        await send_email("plan_downgraded", user_info["email"], {
                            "name": user_info.get("name") or "there",
                            "reason": "payment_failed",
                            "previous_plan": user_info.get("plan", "pro"),
                            "app_url": settings.FRONTEND_URL,
                        })
                else:
                    # Send payment failed warning
                    if user_info and user_info.get("email"):
                        from emails.resend import send_email
                        await send_email("payment_failed", user_info["email"], {
                            "name": user_info.get("name") or "there",
                            "attempt": count,
                            "app_url": settings.FRONTEND_URL,
                        })

        elif event_type == "customer.subscription.deleted":
            customer_id = data.get("customer")
            if customer_id:
                user_info = await _get_user_by_customer(db, customer_id)
                await _update_user_plan(db, customer_id, "free")
                await _reset_failure_count(db, customer_id)
                logger.info("Subscription deleted, downgraded %s to free", customer_id)

                # Send downgrade email
                if user_info and user_info.get("email"):
                    from emails.resend import send_email
                    await send_email("plan_downgraded", user_info["email"], {
                        "name": user_info.get("name") or "there",
                        "reason": "subscription_cancelled",
                        "previous_plan": user_info.get("plan", "pro"),
                        "app_url": settings.FRONTEND_URL,
                    })

        elif event_type == "invoice.paid":
            customer_id = data.get("customer")
            if customer_id:
                await _reset_failure_count(db, customer_id)

    return {"status": "ok"}
