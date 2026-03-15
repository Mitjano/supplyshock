"""Tests for Redis-based rate limiting middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from middleware.rate_limit import check_api_rate_limit, check_rate_limit_generic


def _make_user(plan: str = "free", clerk_id: str = "user_123") -> dict:
    return {
        "sub": clerk_id,
        "email": "test@example.com",
        "public_metadata": {"plan": plan},
    }


def _make_redis(current_count: int = 1):
    """Create a mock Redis that returns current_count on INCR."""
    mock = AsyncMock()
    mock.incr = AsyncMock(return_value=current_count)
    mock.expire = AsyncMock()
    return mock


# ── Tests: check_api_rate_limit ──

@pytest.mark.asyncio
async def test_rate_limit_free_blocked():
    """Free user should get 403 (no API access)."""
    with pytest.raises(HTTPException) as exc_info:
        await check_api_rate_limit(user=_make_user("free"), redis=_make_redis())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "PLAN_REQUIRED"


@pytest.mark.asyncio
async def test_rate_limit_pro_allowed():
    """Pro user within limit should pass."""
    redis = _make_redis(current_count=500)
    result = await check_api_rate_limit(user=_make_user("pro"), redis=redis)
    assert result["sub"] == "user_123"
    redis.incr.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_pro_exceeded():
    """Pro user exceeding 1000 calls should get 429."""
    redis = _make_redis(current_count=1001)

    with pytest.raises(HTTPException) as exc_info:
        await check_api_rate_limit(user=_make_user("pro"), redis=redis)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "RATE_LIMIT_EXCEEDED"
    assert exc_info.value.detail["limit"] == 1000
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_rate_limit_enterprise_unlimited():
    """Enterprise user should skip rate limit entirely."""
    redis = _make_redis()
    result = await check_api_rate_limit(user=_make_user("enterprise"), redis=redis)
    assert result["sub"] == "user_123"
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_business_high_limit():
    """Business user at 9999 calls should still pass."""
    redis = _make_redis(current_count=9999)
    result = await check_api_rate_limit(user=_make_user("business"), redis=redis)
    assert result["sub"] == "user_123"


@pytest.mark.asyncio
async def test_rate_limit_business_exceeded():
    """Business user at 10001 calls should get 429."""
    redis = _make_redis(current_count=10001)

    with pytest.raises(HTTPException) as exc_info:
        await check_api_rate_limit(user=_make_user("business"), redis=redis)

    assert exc_info.value.status_code == 429


# ── Tests: check_rate_limit_generic ──

@pytest.mark.asyncio
async def test_generic_rate_limit_within():
    """Generic rate limit within bounds should return count."""
    redis = _make_redis(current_count=5)
    user = _make_user("pro")
    count = await check_rate_limit_generic(user, "report", limit=10, redis=redis)
    assert count == 5


@pytest.mark.asyncio
async def test_generic_rate_limit_exceeded():
    """Generic rate limit exceeded should raise 429."""
    redis = _make_redis(current_count=11)
    user = _make_user("pro")

    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit_generic(user, "report", limit=10, redis=redis)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["group"] == "report"


@pytest.mark.asyncio
async def test_generic_rate_limit_unlimited():
    """Unlimited (None) should skip check and return 0."""
    redis = _make_redis()
    user = _make_user("enterprise")
    count = await check_rate_limit_generic(user, "report", limit=None, redis=redis)
    assert count == 0
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_sets_ttl_on_first_call():
    """First call (count=1) should set TTL on the key."""
    redis = _make_redis(current_count=1)
    await check_api_rate_limit(user=_make_user("pro"), redis=redis)
    redis.expire.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_no_ttl_on_subsequent():
    """Subsequent calls (count>1) should not set TTL again."""
    redis = _make_redis(current_count=2)
    await check_api_rate_limit(user=_make_user("pro"), redis=redis)
    redis.expire.assert_not_called()
