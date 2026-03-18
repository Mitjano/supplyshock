"""Redis health monitoring — Issue #106.

Checks Redis memory usage, key count, and connectivity.
Alerts if memory usage exceeds 80%.
"""

import logging

import redis

from config import settings

logger = logging.getLogger("supplyshock.monitoring.redis_health")

MEMORY_THRESHOLD_PCT = 80


def check_redis_health() -> dict:
    """Check Redis health: memory, key count, connectivity.

    Returns dict with health metrics and alert status.
    """
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        # Connectivity check
        client.ping()

        info = client.info("memory")
        keyspace = client.info("keyspace")

        used_memory = info.get("used_memory", 0)
        used_memory_human = info.get("used_memory_human", "unknown")
        maxmemory = info.get("maxmemory", 0)
        maxmemory_human = info.get("maxmemory_human", "0B")

        # Calculate usage percentage
        if maxmemory > 0:
            memory_usage_pct = round((used_memory / maxmemory) * 100, 1)
        else:
            # No maxmemory set — can't compute percentage
            memory_usage_pct = None

        # Key count across all DBs
        total_keys = 0
        db_keys = {}
        for db_name, db_info in keyspace.items():
            keys = db_info.get("keys", 0)
            total_keys += keys
            db_keys[db_name] = keys

        alert = False
        if memory_usage_pct is not None and memory_usage_pct > MEMORY_THRESHOLD_PCT:
            alert = True
            logger.warning(
                "REDIS MEMORY ALERT: usage at %.1f%% (%s / %s)",
                memory_usage_pct,
                used_memory_human,
                maxmemory_human,
            )

        return {
            "status": "ok",
            "used_memory": used_memory,
            "used_memory_human": used_memory_human,
            "maxmemory": maxmemory,
            "maxmemory_human": maxmemory_human,
            "memory_usage_pct": memory_usage_pct,
            "total_keys": total_keys,
            "keys_per_db": db_keys,
            "alert": alert,
            "threshold_pct": MEMORY_THRESHOLD_PCT,
        }
    except redis.ConnectionError as e:
        logger.error("Redis connection failed: %s", e)
        return {"status": "error", "error": str(e), "alert": True}
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return {"status": "error", "error": str(e), "alert": True}
    finally:
        client.close()
