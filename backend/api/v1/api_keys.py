"""API Key management — /api/v1/api-keys/*

Users can create and manage API keys for programmatic access.
- POST   /api-keys        — generate a new API key
- GET    /api-keys        — list user's keys (prefix only)
- DELETE /api-keys/{id}   — revoke a key
"""

import hashlib
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the key")


@router.post("")
async def create_api_key(
    body: ApiKeyCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. The full key is returned ONCE — store it safely."""
    user_id = await resolve_user_id(user, db)
    plan = user.get("_db_plan", "free")

    # Plan limits: free = 1 key, pro = 5, business = 20, enterprise = unlimited
    max_keys = {"free": 1, "pro": 5, "business": 20, "enterprise": 1000}.get(plan, 1)
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM api_keys WHERE user_id = :uid AND is_active = TRUE"),
        {"uid": user_id},
    )
    count = count_result.scalar()
    if count >= max_keys:
        raise HTTPException(
            status_code=402,
            detail={"error": f"Your plan allows max {max_keys} active API keys", "code": "PLAN_LIMIT"},
        )

    # Generate key: sk_live_<32 random chars>
    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:16]

    result = await db.execute(
        text("""
            INSERT INTO api_keys (user_id, key_hash, key_prefix, name)
            VALUES (:uid, :hash, :prefix, :name)
            RETURNING id, created_at
        """),
        {"uid": user_id, "hash": key_hash, "prefix": key_prefix, "name": body.name},
    )
    await db.commit()
    row = result.mappings().first()

    return {
        "id": str(row["id"]),
        "key": raw_key,  # Only returned once!
        "key_prefix": key_prefix,
        "name": body.name,
        "created_at": row["created_at"].isoformat(),
        "warning": "Store this key safely — it won't be shown again.",
    }


@router.get("")
async def list_api_keys(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List user's API keys (prefix + metadata only, never the full key)."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, key_prefix, name, is_active, last_used_at, expires_at, created_at
            FROM api_keys
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
                "key_prefix": r["key_prefix"],
                "name": r["name"],
                "is_active": r["is_active"],
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("SELECT id FROM api_keys WHERE id = :kid AND user_id = :uid"),
        {"kid": key_id, "uid": user_id},
    )
    if not result.mappings().first():
        raise HTTPException(status_code=404, detail="API key not found")

    await db.execute(
        text("UPDATE api_keys SET is_active = FALSE WHERE id = :kid"),
        {"kid": key_id},
    )
    await db.commit()

    return {"status": "revoked"}
