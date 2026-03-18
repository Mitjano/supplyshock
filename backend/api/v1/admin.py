"""Admin endpoints — Issue #109.

- GET /admin/ingestion-health — per-source data freshness and health status
"""

from typing import Any

from fastapi import APIRouter, Depends

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit
from monitoring.data_freshness import check_data_freshness
from monitoring.disk_usage import check_db_disk_usage
from monitoring.redis_health import check_redis_health

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/ingestion-health")
async def ingestion_health(
    user: dict[str, Any] = Depends(check_api_rate_limit),
):
    """Per-source ingestion health status.

    Returns data freshness per table, DB disk usage, and Redis health.
    """
    freshness = check_data_freshness()
    disk = check_db_disk_usage()
    redis_health = check_redis_health()

    stale_tables = [t for t in freshness if t.get("stale")]

    overall = "ok"
    if stale_tables:
        overall = "degraded"
    if disk.get("alert") or redis_health.get("alert"):
        overall = "critical"

    return {
        "status": overall,
        "data_freshness": freshness,
        "stale_count": len(stale_tables),
        "db_disk": disk,
        "redis": redis_health,
    }
