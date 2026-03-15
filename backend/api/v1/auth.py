"""Auth endpoints — /api/v1/auth/*

- GET  /auth/me   — return current user from local DB
- POST /auth/sync — create or update user in local DB from Clerk JWT
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _get_db():
    """Yield an async DB session. Imported from main to avoid circular deps."""
    from main import engine

    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@router.get("/me")
async def get_me(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
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
    db: AsyncSession = Depends(_get_db),
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
