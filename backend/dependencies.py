"""Shared FastAPI dependencies used across all route files."""

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
