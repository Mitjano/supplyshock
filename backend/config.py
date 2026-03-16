from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://supplyshock:supplyshock_dev@db:5432/supplyshock"
    DATABASE_URL_SYNC: str = "postgresql://supplyshock:supplyshock_dev@db:5432/supplyshock"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

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

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    SENTRY_DSN: str = ""

    PUBLIC_ENDPOINTS: list[str] = ["/health", "/docs", "/openapi.json", "/api/v1/auth/sync"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
