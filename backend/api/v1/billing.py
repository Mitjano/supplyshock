"""Billing endpoints — /api/v1/billing/*

- POST /billing/checkout  — create Stripe Checkout session
- POST /billing/portal    — create Stripe Customer Portal session
"""

from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from middleware.auth import require_auth

router = APIRouter(prefix="/billing", tags=["Billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICES: dict[str, str] = {
    "pro": "price_pro_monthly",
    "business": "price_business_monthly",
    "enterprise": "price_enterprise_monthly",
}


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


class CheckoutRequest(BaseModel):
    plan: str  # "pro", "business", "enterprise"
    success_url: str = "http://localhost:5173/settings?billing=success"
    cancel_url: str = "http://localhost:5173/settings?billing=cancel"


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Create a Stripe Checkout session for plan upgrade."""
    if body.plan not in PLAN_PRICES:
        raise HTTPException(400, detail={"error": "Invalid plan", "code": "INVALID_PLAN"})

    clerk_id = user.get("sub")

    # Get user from DB
    result = await db.execute(
        text("SELECT id, email, stripe_customer_id, plan FROM users WHERE clerk_user_id = :cid"),
        {"cid": clerk_id},
    )
    user_row = result.mappings().first()
    if not user_row:
        raise HTTPException(404, detail={"error": "User not found", "code": "USER_NOT_FOUND"})

    if user_row["plan"] == body.plan:
        raise HTTPException(400, detail={"error": "Already on this plan", "code": "SAME_PLAN"})

    # Get or create Stripe customer
    customer_id = user_row["stripe_customer_id"]
    if not customer_id:
        customer = stripe.Customer.create(
            email=user_row["email"],
            metadata={"clerk_user_id": clerk_id},
        )
        customer_id = customer.id
        await db.execute(
            text("UPDATE users SET stripe_customer_id = :cid WHERE clerk_user_id = :clerk_id"),
            {"cid": customer_id, "clerk_id": clerk_id},
        )
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICES[body.plan], "quantity": 1}],
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        metadata={"clerk_user_id": clerk_id, "plan": body.plan},
    )

    return {"data": {"checkout_url": session.url, "session_id": session.id}}


@router.post("/portal")
async def create_portal_session(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    clerk_id = user.get("sub")

    result = await db.execute(
        text("SELECT stripe_customer_id FROM users WHERE clerk_user_id = :cid"),
        {"cid": clerk_id},
    )
    user_row = result.mappings().first()
    if not user_row or not user_row["stripe_customer_id"]:
        raise HTTPException(400, detail={"error": "No billing account", "code": "NO_BILLING"})

    session = stripe.billing_portal.Session.create(
        customer=user_row["stripe_customer_id"],
        return_url="http://localhost:5173/settings",
    )

    return {"data": {"portal_url": session.url}}
