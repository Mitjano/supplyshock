import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
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
from api.v1.alert_subscriptions import router as alert_subscriptions_router
from api.v1.billing import router as billing_router
from api.v1.simulations import router as simulations_router
from api.v1.reports import router as reports_router
from api.v1.api_keys import router as api_keys_router
from api.v1.search import router as search_router
from api.v1.voyages import router as voyages_router
from webhooks.stripe import router as stripe_webhook_router

# ── Sentry ──
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=settings.APP_ENV,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
        ],
    )

app = FastAPI(
    title="SupplyShock API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ── CORS ──
# Merge configured origins with FRONTEND_URL to ensure the frontend is always allowed
cors_origins = list(set(settings.CORS_ORIGINS + [settings.FRONTEND_URL]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
redis_client = aioredis.from_url(settings.REDIS_URL)


@app.get("/health")
async def health_check():
    import json

    db_status = "ok"
    redis_status = "ok"
    celery_status = "unknown"
    celery_workers = 0

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"

    # Check Celery health from Redis heartbeat (written by celery_health_check task)
    try:
        health_data = await redis_client.get("celery:health")
        if health_data:
            parsed = json.loads(health_data)
            celery_workers = parsed.get("worker_count", 0)
            celery_status = "ok" if celery_workers > 0 else "no_workers"
        else:
            celery_status = "no_heartbeat"
    except Exception:
        celery_status = "error"

    all_ok = db_status == "ok" and redis_status == "ok"
    status = "ok" if all_ok else "degraded"
    return {
        "status": status,
        "db": db_status,
        "redis": redis_status,
        "celery": celery_status,
        "celery_workers": celery_workers,
    }


# ── API v1 routers ──
app.include_router(auth_router, prefix="/api/v1")
app.include_router(vessels_router, prefix="/api/v1")
app.include_router(ports_router, prefix="/api/v1")
app.include_router(commodities_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(bottlenecks_router, prefix="/api/v1")
app.include_router(alert_subscriptions_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(simulations_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(voyages_router, prefix="/api/v1")

# ── Webhooks (no /api/v1 prefix) ──
app.include_router(stripe_webhook_router)
