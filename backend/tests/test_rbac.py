"""Tests for plan-based RBAC middleware.

Tests use direct function calls with mocked dependencies,
no need for a running database.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from auth.rbac import (
    require_plan,
    check_simulation_limit,
    _get_user_plan,
    PLAN_HIERARCHY,
    SIMULATION_LIMITS,
)


# ── Helper: fake JWT payloads ──

def _make_user(plan: str = "free", clerk_id: str = "user_123") -> dict:
    return {
        "sub": clerk_id,
        "email": "test@example.com",
        "public_metadata": {"plan": plan},
    }


# ── Tests: _get_user_plan ──

def test_get_user_plan_free():
    assert _get_user_plan(_make_user("free")) == "free"


def test_get_user_plan_pro():
    assert _get_user_plan(_make_user("pro")) == "pro"


def test_get_user_plan_missing_metadata():
    user = {"sub": "user_123", "email": "test@example.com"}
    assert _get_user_plan(user) == "free"


# ── Tests: require_plan ──

@pytest.mark.asyncio
async def test_rbac_free_blocked():
    """Free user should be blocked by require_plan('pro')."""
    check = require_plan("pro")
    free_user = _make_user("free")

    with pytest.raises(HTTPException) as exc_info:
        await check(user=free_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "PLAN_REQUIRED"
    assert exc_info.value.detail["required_plan"] == "pro"
    assert exc_info.value.detail["current_plan"] == "free"


@pytest.mark.asyncio
async def test_rbac_pro_allowed():
    """Pro user should pass require_plan('pro')."""
    check = require_plan("pro")
    pro_user = _make_user("pro")

    result = await check(user=pro_user)
    assert result["sub"] == "user_123"


@pytest.mark.asyncio
async def test_rbac_business_passes_pro():
    """Business user should pass require_plan('pro') — higher tier."""
    check = require_plan("pro")
    biz_user = _make_user("business")

    result = await check(user=biz_user)
    assert result["sub"] == "user_123"


@pytest.mark.asyncio
async def test_rbac_enterprise_passes_all():
    """Enterprise passes any plan check."""
    for plan in ["free", "pro", "business"]:
        check = require_plan(plan)
        ent_user = _make_user("enterprise")
        result = await check(user=ent_user)
        assert result["sub"] == "user_123"


@pytest.mark.asyncio
async def test_rbac_free_blocked_by_business():
    """Free user blocked by require_plan('business')."""
    check = require_plan("business")

    with pytest.raises(HTTPException) as exc_info:
        await check(user=_make_user("free"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_rbac_pro_blocked_by_business():
    """Pro user blocked by require_plan('business')."""
    check = require_plan("business")

    with pytest.raises(HTTPException) as exc_info:
        await check(user=_make_user("pro"))
    assert exc_info.value.status_code == 403


# ── Tests: check_simulation_limit ──

@pytest.mark.asyncio
async def test_simulation_limit_free_blocked():
    """Free user with 3 simulations this month should be blocked."""
    free_user = _make_user("free")

    # Mock DB session that returns count=3
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await check_simulation_limit(user=free_user, db=mock_db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "SIMULATION_LIMIT_REACHED"
    assert exc_info.value.detail["limit"] == 3
    assert exc_info.value.detail["used"] == 3


@pytest.mark.asyncio
async def test_simulation_limit_free_allowed():
    """Free user with 2 simulations this month should pass."""
    free_user = _make_user("free")

    mock_result = MagicMock()
    mock_result.scalar.return_value = 2
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await check_simulation_limit(user=free_user, db=mock_db)
    assert result["sub"] == "user_123"


@pytest.mark.asyncio
async def test_simulation_limit_business_unlimited():
    """Business user should skip the check entirely (unlimited)."""
    biz_user = _make_user("business")

    # DB should NOT be called for unlimited plans
    mock_db = AsyncMock()
    result = await check_simulation_limit(user=biz_user, db=mock_db)
    assert result["sub"] == "user_123"
    mock_db.execute.assert_not_called()
