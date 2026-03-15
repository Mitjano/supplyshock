"""Plan-based RBAC decorators for FastAPI endpoints.

Usage:
    @router.get("/simulations")
    async def list_sims(user: dict = Depends(require_plan("pro"))):
        ...

    @router.post("/simulations")
    async def create_sim(user: dict = Depends(check_simulation_limit)):
        ...
"""

from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

# Plan hierarchy — higher index = more privileges
PLAN_HIERARCHY = {
    "free": 0,
    "pro": 1,
    "business": 2,
    "enterprise": 3,
}

# Monthly simulation limits per plan
SIMULATION_LIMITS = {
    "free": 3,
    "pro": 50,
    "business": None,  # unlimited
    "enterprise": None,  # unlimited
}

# Daily report limits per plan
REPORT_LIMITS = {
    "free": 1,
    "pro": 10,
    "business": 100,
    "enterprise": None,
}


async def _get_db():
    """Yield an async DB session."""
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


def _get_user_plan(user: dict[str, Any]) -> str:
    """Extract plan from JWT payload or default to 'free'."""
    # Clerk stores plan in publicMetadata
    metadata = user.get("public_metadata", user.get("publicMetadata", {}))
    if isinstance(metadata, dict):
        return metadata.get("plan", "free")
    return "free"


def require_plan(minimum_plan: str):
    """FastAPI dependency factory — blocks users below the required plan.

    Usage: Depends(require_plan("pro"))
    """
    min_level = PLAN_HIERARCHY.get(minimum_plan, 0)

    async def _check(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
        user_plan = _get_user_plan(user)
        user_level = PLAN_HIERARCHY.get(user_plan, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": f"This feature requires the {minimum_plan} plan or higher",
                    "code": "PLAN_REQUIRED",
                    "required_plan": minimum_plan,
                    "current_plan": user_plan,
                },
            )
        return user

    return _check


async def check_simulation_limit(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    """FastAPI dependency — checks monthly simulation count against plan limit.

    Raises 403 with SIMULATION_LIMIT_REACHED if limit exceeded.
    """
    user_plan = _get_user_plan(user)
    limit = SIMULATION_LIMITS.get(user_plan)

    # Unlimited plans skip the check
    if limit is None:
        return user

    clerk_user_id = user.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail={"error": "Invalid token", "code": "INVALID_TOKEN"})

    # Count simulations this month
    result = await db.execute(
        text("""
            SELECT COUNT(*) as cnt FROM simulations s
            JOIN users u ON u.id = s.user_id
            WHERE u.clerk_user_id = :clerk_id
              AND s.created_at >= date_trunc('month', NOW())
        """),
        {"clerk_id": clerk_user_id},
    )
    count = result.scalar() or 0

    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"Monthly simulation limit reached ({limit} per month on {user_plan} plan)",
                "code": "SIMULATION_LIMIT_REACHED",
                "limit": limit,
                "used": count,
                "current_plan": user_plan,
            },
        )

    return user


async def check_report_limit(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    """FastAPI dependency — checks daily report count against plan limit."""
    user_plan = _get_user_plan(user)
    limit = REPORT_LIMITS.get(user_plan)

    if limit is None:
        return user

    clerk_user_id = user.get("sub")
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail={"error": "Invalid token", "code": "INVALID_TOKEN"})

    result = await db.execute(
        text("""
            SELECT COUNT(*) as cnt FROM reports r
            JOIN users u ON u.id = r.user_id
            WHERE u.clerk_user_id = :clerk_id
              AND r.created_at >= date_trunc('day', NOW())
        """),
        {"clerk_id": clerk_user_id},
    )
    count = result.scalar() or 0

    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error": f"Daily report limit reached ({limit} per day on {user_plan} plan)",
                "code": "REPORT_LIMIT_REACHED",
                "limit": limit,
                "used": count,
                "current_plan": user_plan,
            },
        )

    return user
