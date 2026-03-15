import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings
from api.v1.auth import router as auth_router
from api.v1.vessels import router as vessels_router
from api.v1.ports import router as ports_router
from api.v1.commodities import router as commodities_router
from api.v1.alerts import router as alerts_router
from api.v1.bottlenecks import router as bottlenecks_router

app = FastAPI(
    title="SupplyShock API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
redis_client = aioredis.from_url(settings.REDIS_URL)


@app.get("/health")
async def health_check():
    db_status = "ok"
    redis_status = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"

    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {"status": status, "db": db_status, "redis": redis_status}


# ── API v1 routers ──
app.include_router(auth_router, prefix="/api/v1")
app.include_router(vessels_router, prefix="/api/v1")
app.include_router(ports_router, prefix="/api/v1")
app.include_router(commodities_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(bottlenecks_router, prefix="/api/v1")
