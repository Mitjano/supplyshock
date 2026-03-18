# Redis Key Namespace Documentation — Issue #106

## Database Allocation

| DB | Purpose | Config Key |
|----|---------|------------|
| 0 | Application cache, rate limiting, pub/sub | `REDIS_URL` |
| 1 | Celery broker (task queue messages) | `CELERY_BROKER_URL` |
| 2 | Celery result backend (task results) | `CELERY_RESULT_BACKEND` |

## DB 0 — Key Namespaces

### Rate Limiting
- **Pattern**: `rl:{clerk_user_id}:{group}:{date}`
- **Example**: `rl:user_2abc123:default:2026-03-18`
- **TTL**: 26 hours (daily counters), 32 days (monthly counters)
- **Type**: String (counter via INCR)

### Celery Health
- **Key**: `celery:health`
- **TTL**: 5 minutes
- **Type**: String (JSON blob)
- **Schema**: `{"worker_count": int, "active_tasks": int, "timestamp": ISO8601}`

### Pub/Sub Channels
- **Channel**: `alerts` — real-time alert events broadcast to SSE clients
- **Payload**: JSON `{"type": str, "severity": str, "title": str, ...}`

### Cache Keys
- **Pattern**: `cache:{endpoint}:{params_hash}`
- **TTL**: varies per endpoint (60s–3600s)
- **Type**: String (JSON response)

### Session/Auth
- **Pattern**: `session:{session_id}`
- **TTL**: 24 hours
- **Type**: String (JSON)

## DB 1 — Celery Broker
Managed by Celery. Do not manually write keys here.
- Queue keys: `ais`, `ingestion`, `analytics` (as of Issue #103)

## DB 2 — Celery Results
Managed by Celery. Task result keys auto-expire based on `result_expires` setting.

## Memory Guidelines
- Monitor with `INFO memory` — alert if `used_memory` > 80% of `maxmemory`
- Set `maxmemory-policy allkeys-lru` in production
- Expected steady-state: ~50–200 MB depending on active sessions and cache
