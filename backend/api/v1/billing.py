"""Billing endpoints — /api/v1/billing/*

- POST /billing/checkout  — create Stripe Checkout session
- POST /billing/portal    — create Stripe Customer Portal session
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from dependencies import get_db, resolve_user_id
from middleware.auth import require_auth

logger = logging.getLogger("billing")

router = APIRouter(prefix="/billing", tags=["Billing"])

# Stripe Price IDs (configured in Stripe dashboard)
PLAN_PRICES = {
    "pro": "price_pro_monthly",       # Replace with real Stripe price IDs
    "business": "price_business_monthly",
}


class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Target plan: pro, business")


class PortalRequest(BaseModel):
    return_url: str | None = Field(None, description="URL to return to after portal")


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for plan upgrade."""
    import stripe

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    if body.plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")

    user_id = await resolve_user_id(user, db)
    clerk_id = user.get("sub")
    email = user.get("email", "")

    # Get or create Stripe customer
    result = await db.execute(
        text("SELECT stripe_customer_id, email FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    row = result.mappings().first()
    stripe_customer_id = row["stripe_customer_id"] if row else None
    email = row["email"] if row else email

    if not stripe_customer_id:
        customer = stripe.Customer.create(
            email=email,
            metadata={"clerk_user_id": clerk_id, "user_id": user_id},
        )
        stripe_customer_id = customer.id
        await db.execute(
            text("UPDATE users SET stripe_customer_id = :sid WHERE id = :uid"),
            {"sid": stripe_customer_id, "uid": user_id},
        )
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICES[body.plan], "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/settings?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/settings?checkout=cancel",
        metadata={"user_id": user_id, "plan": body.plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal(
    body: PortalRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for subscription management."""
    import stripe

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("SELECT stripe_customer_id FROM users WHERE id = :uid"),
        {"uid": user_id},
    )
    row = result.mappings().first()
    if not row or not row["stripe_customer_id"]:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=row["stripe_customer_id"],
        return_url=body.return_url or f"{settings.FRONTEND_URL}/settings",
    )

    return {"portal_url": session.url}
