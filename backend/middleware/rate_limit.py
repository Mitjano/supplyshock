"""Redis-based rate limiting middleware per plan per endpoint group.

Key format: rl:{user_id}:{group}:{date}
Groups: simulation, report, api_calls

Usage:
    @router.get("/data")
    async def get_data(user: dict = Depends(check_api_rate_limit)):
        ...
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, Response

from middleware.auth import require_auth
from auth.rbac import _get_user_plan

# Daily API call limits per plan
API_CALL_LIMITS = {
    "free": 0,  # No API access
    "pro": 1_000,
    "business": 10_000,
    "enterprise": None,  # unlimited
}

# TTL for rate limit keys (26 hours — covers timezone edge cases)
KEY_TTL_SECONDS = 26 * 3600


async def _get_redis():
    """Get Redis client from main module."""
    from main import redis_client
    return redis_client


async def check_api_rate_limit(
    user: dict[str, Any] = Depends(require_auth),
    redis=Depends(_get_redis),
) -> dict[str, Any]:
    """FastAPI dependency — checks daily API call count via Redis INCR.

    Raises 429 with Retry-After header if limit exceeded.
    """
    user_plan = _get_user_plan(user)
    limit = API_CALL_LIMITS.get(user_plan)

    # Unlimited plans skip the check
    if limit is None:
        return user

    # Free plan has no API access at all
    if limit == 0:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "API access requires a Pro plan or higher",
                "code": "PLAN_REQUIRED",
                "required_plan": "pro",
                "current_plan": user_plan,
            },
        )

    clerk_user_id = user.get("sub", "unknown")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"rl:{clerk_user_id}:api_calls:{today}"

    # Atomic increment
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, KEY_TTL_SECONDS)

    if current > limit:
        # Calculate seconds until midnight UTC
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_next = midnight.replace(day=midnight.day + 1) if midnight < now else midnight
        retry_after = int((midnight_next - now).total_seconds())

        raise HTTPException(
            status_code=429,
            detail={
                "error": f"Daily API call limit reached ({limit} per day on {user_plan} plan)",
                "code": "RATE_LIMIT_EXCEEDED",
                "limit": limit,
                "used": current,
                "current_plan": user_plan,
            },
            headers={"Retry-After": str(retry_after)},
        )

    return user


async def check_rate_limit_generic(
    user: dict[str, Any],
    group: str,
    limit: int | None,
    redis,
    period: str = "day",
) -> int:
    """Generic rate limit check. Returns current count.

    Args:
        user: JWT payload
        group: endpoint group name (e.g. "simulation", "report")
        limit: max allowed count, None for unlimited
        redis: Redis client
        period: "day" or "month"

    Returns current count. Raises 429 if exceeded.
    """
    if limit is None:
        return 0

    clerk_user_id = user.get("sub", "unknown")

    if period == "day":
        date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
        ttl = KEY_TTL_SECONDS
    else:
        date_key = datetime.now(timezone.utc).strftime("%Y%m")
        ttl = 32 * 24 * 3600  # ~32 days

    key = f"rl:{clerk_user_id}:{group}:{date_key}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, ttl)

    if current > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": f"Rate limit reached for {group} ({limit} per {period})",
                "code": "RATE_LIMIT_EXCEEDED",
                "limit": limit,
                "used": current,
                "group": group,
            },
            headers={"Retry-After": "3600"},
        )

    return current
