from pydantic_settings import BaseSettings


# Redis database allocation:
#   DB 0 — Application cache + rate limiting + pub/sub
#           Key namespaces:
#             rl:{clerk_user_id}:{group}:{date}  — rate limit counters (TTL: 26h-32d)
#             celery:health                       — worker heartbeat JSON (TTL: 5min)
#             alerts                              — pub/sub channel for real-time alerts
#   DB 1 — Celery broker (task queue messages)
#   DB 2 — Celery result backend (task results)


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://supplyshock:supplyshock_dev@db:5432/supplyshock"
    DATABASE_URL_SYNC: str = "postgresql://supplyshock:supplyshock_dev@db:5432/supplyshock"
    REDIS_URL: str = "redis://redis:6379/0"          # DB 0: app cache + rate limiting
    CELERY_BROKER_URL: str = "redis://redis:6379/1"   # DB 1: Celery broker
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"  # DB 2: Celery results

    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    CLERK_JWKS_URL: str = ""  # Override auto-derived JWKS URL if needed
    AISSTREAM_API_KEY: str = ""
    EIA_API_KEY: str = ""
    NASDAQ_DATA_LINK_API_KEY: str = ""
    COMTRADE_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    ZEP_API_KEY: str = ""

    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    SENTRY_DSN: str = ""

    PUBLIC_ENDPOINTS: list[str] = ["/health", "/docs", "/openapi.json", "/api/v1/auth/sync"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
