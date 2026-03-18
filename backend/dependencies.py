"""Shared FastAPI dependencies used across all route files."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncSession:
    """Yield an async DB session. Imported from main to avoid circular deps."""
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


async def get_redis():
    """Get Redis client from main module."""
    from main import redis_client
    return redis_client


async def resolve_user_id(user: dict[str, Any], db: AsyncSession) -> str:
    """Resolve Clerk JWT `sub` to database user UUID.

    Returns the users.id as a string. Raises 404 if user not found in DB.
    """
    clerk_id = user.get("sub")
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        text("SELECT id, plan FROM users WHERE clerk_user_id = :cid"),
        {"cid": clerk_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    # Inject DB fields into user dict for downstream use
    user["_db_user_id"] = str(row["id"])
    user["_db_plan"] = row["plan"]
    return str(row["id"])
