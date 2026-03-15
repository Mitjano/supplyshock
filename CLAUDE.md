# SupplyShock — Project Context for Claude Code

> Read this file before touching any code. It is the single source of truth for
> conventions, architecture, and rules. When in doubt: check here first.

---

## Quick start (run this first)

```bash
git clone https://github.com/YOUR_HANDLE/supplyshock.git
cd supplyshock
cp .env.example .env          # fill in at minimum: CLERK_*, MAPBOX_ACCESS_TOKEN, AISSTREAM_API_KEY
docker compose up -d          # starts db, redis, backend, celery, frontend
docker compose exec backend alembic upgrade head   # run migrations (auto on start too)
open http://localhost:5173    # frontend
open http://localhost:8000/docs  # FastAPI swagger UI
```

To verify everything is running: `docker compose ps` — all services should be healthy.
To run tests: `docker compose exec backend pytest -x`
To see backend logs: `docker compose logs -f backend`

---

## What this project is

**SupplyShock** is an open-source SaaS platform for monitoring and predicting global
commodity supply chains. It ingests live AIS vessel data, commodity prices, news events,
and trade flow data, then exposes analytics, anomaly alerts, and multi-agent scenario
simulations to paying subscribers.

**Target user:** commodity analyst, trader, or logistics manager who needs one tool
combining vessel tracking + price signals + supply chain risk.

**Monetization:** Free / Pro ($99/mo) / Business ($499/mo) / Enterprise (custom).

---

## Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.12 + FastAPI | All API in `/backend` |
| Database | PostgreSQL 16 + TimescaleDB 2.x | One instance, two roles |
| Cache / pub-sub | Redis 7 | Sessions, rate limits, SSE |
| Task queue | Celery 5 + Redis broker | Long-running simulations |
| Simulation | OASIS (CAMEL-AI) + Zep Cloud | Agent memory |
| Frontend | Vue 3 + Vite + Pinia | In `/frontend` |
| Map | Mapbox GL JS + Deck.gl | Vessel rendering |
| Auth | Clerk | Google + email + GitHub OAuth |
| Payments | Stripe | Webhooks in `/backend/webhooks` |
| Email | Resend + React Email | Transactional only |
| Reverse proxy | Nginx | TLS termination via Let's Encrypt |
| Containers | Docker + Docker Compose | One compose file per environment |
| CI | GitHub Actions | Lint → test → build → deploy |

---

## Directory structure

```
supplyshock/
├── CLAUDE.md                  ← you are here
├── .env.example               ← all required env vars documented here, NO values
├── docker-compose.yml         ← local dev
├── docker-compose.prod.yml    ← production
├── openapi.yaml               ← API contract — read before writing any endpoint
├── schema.sql                 ← database schema — source of truth for all tables
│
├── backend/
│   ├── main.py                ← FastAPI app entry point
│   ├── config.py              ← settings loaded from env vars via pydantic-settings
│   ├── auth/
│   │   ├── clerk.py           ← Clerk JWT verification
│   │   └── rbac.py            ← plan-based permission checks
│   ├── api/
│   │   └── v1/                ← ALL endpoints prefixed /api/v1/
│   │       ├── vessels.py
│   │       ├── commodities.py
│   │       ├── alerts.py
│   │       ├── simulations.py
│   │       ├── reports.py
│   │       └── billing.py
│   ├── ingestion/
│   │   ├── ais_stream.py      ← aisstream.io WebSocket consumer
│   │   ├── gdelt.py           ← GDELT news poller (15min interval)
│   │   ├── eia.py             ← EIA energy data
│   │   └── comtrade.py        ← UN Comtrade trade flows
│   ├── simulation/
│   │   ├── engine.py          ← OASIS orchestration
│   │   ├── tasks.py           ← Celery tasks
│   │   ├── poc_newcastle.py   ← POC script (Issue #26)
│   │   └── oasis_fork/        ← local OASIS fork with commodity extensions
│   │       ├── commodity/     ← toolkits.py, agents.py, market.py
│   │       ├── social_platform/ ← modified: typing, platform, database, schema/
│   │       ├── social_agent/  ← modified: agent.py, agent_environment.py
│   │       └── environment/   ← modified: env.py
│   ├── webhooks/
│   │   └── stripe.py          ← Stripe webhook handler
│   ├── middleware/
│   │   ├── rate_limit.py      ← per-plan rate limiting via Redis
│   │   └── auth.py            ← JWT middleware
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── views/             ← Map, Commodities, Bottlenecks, Simulation, Reports
│   │   ├── components/
│   │   ├── layouts/           ← LocaleLayout.vue (locale guard)
│   │   ├── composables/       ← useLocale.ts, usePageMeta.ts
│   │   ├── stores/            ← Pinia stores (useAuthStore, useMapStore, etc.)
│   │   ├── api/               ← typed API client (auto-generated from openapi.yaml)
│   │   ├── i18n.ts            ← vue-i18n config, lazy loading per locale
│   │   └── locales/
│   │       ├── pl/            ← common, map, commodities, bottlenecks, simulation, reports, billing, auth
│   │       └── en/            ← same keys, natural English translations
│   └── tests/
│
└── infra/
    ├── nginx.conf
    └── certbot/
```

---

## Database rules

**TimescaleDB hypertables** (time-series, high insert rate):
- `vessel_positions` — partition by `time` (1 week chunks)
- `commodity_prices` — partition by `time` (1 month chunks)
- `alert_events` — partition by `time` (1 week chunks)

**PostgreSQL tables** (relational, low insert rate):
- `users`, `subscriptions`, `api_keys`, `simulations`, `reports`, `ports`, `trade_flows`


**Alembic migrations** — how to work with schema changes:
- Config: `backend/migrations/alembic.ini` and `backend/migrations/env.py`
- Alembic uses `DATABASE_URL_SYNC` (sync psycopg2 driver), NOT `DATABASE_URL` (async asyncpg)
- Generate new migration: `docker compose exec backend alembic revision --autogenerate -m "add_column_x"`
- Apply migrations: `docker compose exec backend alembic upgrade head`
- Rollback one step: `docker compose exec backend alembic downgrade -1`
- Never edit `schema.sql` in production — always use Alembic migrations

**Migration rule:** Never modify `schema.sql` directly in production. All schema changes
go through Alembic migrations in `backend/migrations/`. Run `alembic upgrade head` on deploy.

**Never write raw SQL in application code.** Use SQLAlchemy ORM or asyncpg with
parameterized queries. No string interpolation in queries — ever.

---

## API rules

**Every endpoint must:**
1. Be prefixed `/api/v1/`
2. Match the contract in `openapi.yaml` — if you need a new endpoint, update openapi.yaml first
3. Require auth (Clerk JWT) unless explicitly listed in `PUBLIC_ENDPOINTS` in `config.py`
4. Check plan permissions via `rbac.py` for simulation/report/API key endpoints
5. Return errors as `{"error": "message", "code": "ERROR_CODE"}` JSON, never plain text
6. Include `X-Request-ID` header in responses

**Response format:**
```json
{
  "data": { ... },
  "meta": { "page": 1, "total": 100 }
}
```

**HTTP status codes:**
- 200 success, 201 created, 204 no content
- 400 bad request (validation), 401 unauthenticated, 403 forbidden (plan limit)
- 404 not found, 422 unprocessable entity, 429 rate limited, 500 server error

---

## Auth rules

**Clerk is the only auth provider.** Do not implement custom JWT generation.

**Flow:**
1. Frontend calls Clerk SDK → gets JWT token
2. Every API request sends `Authorization: Bearer <clerk_jwt>`
3. `auth/clerk.py` verifies signature against Clerk JWKS endpoint
4. Decoded payload contains `user_id`, `email`, `plan` (stored in Clerk metadata)

**Plan metadata keys** (stored in Clerk `publicMetadata`):
```json
{
  "plan": "free|pro|business|enterprise",
  "plan_expires_at": "2026-12-31T00:00:00Z",
  "api_calls_limit": 0,
  "simulations_limit": 3
}
```

**RBAC checks** — `rbac.py` exposes these decorators:
- `@require_plan("pro")` — blocks Free users
- `@require_plan("business")` — blocks Free + Pro
- `@check_simulation_limit` — checks monthly simulation count
- `@check_api_rate_limit` — Redis INCR per user per day

---

## Security rules — READ CAREFULLY

**NEVER commit secrets.** If you need a secret: add it to `.env.example` as
`SECRET_NAME=` (empty value) and load it in `config.py` via `pydantic-settings`.
The `.gitignore` already excludes `.env`. If you see a hardcoded key anywhere in
the codebase, remove it immediately and rotate the key.

**Required env vars** (all in `.env.example`):
```
CLERK_SECRET_KEY=
CLERK_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
CLAUDE_API_KEY=
MAPBOX_ACCESS_TOKEN=
AISSTREAM_API_KEY=
EIA_API_KEY=
DATABASE_URL=
REDIS_URL=
RESEND_API_KEY=
ZEP_API_KEY=
COMTRADE_API_KEY=
STRIPE_PRICE_PRO=
STRIPE_PRICE_BUSINESS=
CLERK_WEBHOOK_SECRET=
SUPPLYSHOCK_DB_URL=         # same as DATABASE_URL — used by oasis_fork toolkits
```

**Input validation:** Use Pydantic models for all request bodies. No raw `request.json()`
without a Pydantic schema. Validate all query parameters with FastAPI's type system.

**CORS:** In production, allow only `https://supplyshock.io`. In development,
allow `http://localhost:5173`. Never use `allow_origins=["*"]` in production.

**HTTPS:** All production traffic goes through Nginx with Let's Encrypt cert.
Backend never handles TLS — only Nginx does.

**Security headers** (set in Nginx, not in FastAPI):
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; ...
```

---

## Rate limiting

Limits enforced per user per endpoint category, tracked in Redis:

| Plan | Simulations/mo | API calls/day | Reports/day | Map requests |
|---|---|---|---|---|
| Free | 3 | 0 (no API) | 1 | unlimited |
| Pro | 50 | 1,000 | 10 | unlimited |
| Business | unlimited | 10,000 | 100 | unlimited |
| Enterprise | unlimited | custom | unlimited | unlimited |

**Implementation:** `middleware/rate_limit.py` uses Redis key `rl:{user_id}:{endpoint_group}:{period}`
with TTL matching the period. Returns 429 with `Retry-After` header on breach.

---

## Stripe billing rules

**Products and Prices** are created manually in Stripe dashboard. Their IDs are stored
in environment variables, not hardcoded:
```
STRIPE_PRICE_PRO=price_xxx
STRIPE_PRICE_BUSINESS=price_xxx
```

**Webhook events to handle** (in `webhooks/stripe.py`):
- `checkout.session.completed` → update user plan in Clerk metadata + `subscriptions` table
- `invoice.payment_succeeded` → extend `plan_expires_at`
- `invoice.payment_failed` → send warning email, downgrade to Free after 3 failures
- `customer.subscription.deleted` → immediately downgrade to Free
- `customer.subscription.updated` → sync plan changes (upgrades/downgrades)

**Always verify Stripe webhook signature** using `STRIPE_WEBHOOK_SECRET`. Never process
an event without signature verification.

---

## Celery / async tasks

**Long-running operations go to Celery, never block the HTTP thread:**
- Simulation runs (`simulation/tasks.py`)
- PDF report generation
- Batch data ingestion

**Task result polling:** Client polls `GET /api/v1/simulations/{job_id}` which reads
Celery task state from Redis. For progress streaming: use Server-Sent Events (SSE)
on `GET /api/v1/simulations/{job_id}/stream`.

**Task timeout:** Simulations timeout after 10 minutes. Reports after 2 minutes.
Always set `task_time_limit` in Celery task decorator.

---

## Simulation framework — OASIS commodity fork

**Lokalizacja forka:** `backend/simulation/oasis_fork/`
Nigdy nie modyfikuj zainstalowanego pakietu `camel-oasis`. Pracuj wyłącznie na lokalnej kopii w `oasis_fork/`.

**Co zostało zmodyfikowane w stosunku do upstream OASIS:**

| Plik | Zmiana |
|------|--------|
| `social_platform/typing.py` | +5 ActionType: SUBMIT_TRADE, REROUTE_VESSEL, UPDATE_PRICE_VIEW, IMPOSE_MEASURE, ACTIVATE_INVENTORY |
| `social_platform/platform.py` | +5 async handlers (jeden per nowy ActionType) |
| `social_platform/database.py` | ładuje 3 commodity schema files |
| `social_platform/schema/trade.sql` | nowa tabela decyzji handlowych |
| `social_platform/schema/market_state.sql` | nowa tabela consensus cenowego |
| `social_agent/agent.py` | routing do CommodityEnvironment jeśli CommodityAgentInfo |
| `social_agent/agent_environment.py` | +CommodityEnvironment subclass |
| `social_platform/config/user.py` | +CommodityAgentInfo dataclass |
| `environment/env.py` | +COMMODITY w OasisEnv.__init__ |
| `commodity/` (nowy moduł) | toolkits.py, agents.py, market.py |

**Kluczowe reguły dla Claude Code przy pracy z oasis_fork:**

1. **Max 3 parametry per platform handler** (platform.py L155 hardcoded check). Każdy handler: `self, agent_id, message_tuple`. Pakuj wiele wartości w tuple.

2. **FunctionTool wymaga pełnego docstring** — CAMEL buduje tool schema z docstring. Obowiązkowy format z Args i Returns — bez tego CAMEL rzuca wyjątek przy tworzeniu agenta.

3. **getattr pattern** — `action.value == "submit_trade"` musi dokładnie odpowiadać nazwie metody w Platform. Błąd w nazwie = `ValueError: Action is not supported`.

4. **CommodityEnvironment.to_text_prompt() musi być async** — rodzic jest async, subclass też.

5. **Używaj DefaultPlatformType.COMMODITY** w symulacjach commodity, nie REDDIT/TWITTER.

**Typy agentów i koszt:**

| Typ | Akcje | Model | Koszt/symulację |
|-----|-------|-------|-----------------|
| coal_trader | SUBMIT_TRADE, UPDATE_PRICE_VIEW | Claude Haiku | ~$0.02 |
| bulk_shipper | REROUTE_VESSEL | ManualAction rule-based | $0 |
| government | IMPOSE_MEASURE, ACTIVATE_INVENTORY | Claude Haiku | ~$0.04 |
| refinery | ACTIVATE_INVENTORY | ManualAction threshold | $0 |

**Seed event pattern** — jak wstrzyknąć scenariusz:
Krok 0: system_feed_agent postuje `ManualAction(CREATE_POST, {"content": "BREAKING: [opis scenariusza]"})`.
Krok 1+: LLM agenci widzą ten post przez rec system i reagują swoimi decyzjami.

**Price discovery** — cena wyłania się z emergencji:
Agent widzi disruption → submit_trade z price_view → zapisuje do market_state → inni agenci widzą w feedzie zakupy → podnoszą swój price_view → compute_consensus_price() agreguje AVG(price_view) → to jest wyłaniająca się "cena rynkowa".

## i18n — internacjonalizacja (PL / EN)

**Technologia:** vue-i18n v9 z lazy loading per locale.

**URL routing:** prefiks języka na wszystkich trasach:
- `supplyshock.pl/pl/map` — wersja polska
- `supplyshock.pl/en/map` — wersja angielska
- `supplyshock.pl/` → auto-detect język przeglądarki → redirect do /pl lub /en

**Struktura plików:**
```
frontend/src/locales/
├── pl/
│   ├── common.json       ← nav, buttons, errors, dates
│   ├── map.json          ← mapa, statki, cieśniny
│   ├── commodities.json  ← surowce, ceny, przepływy
│   ├── bottlenecks.json  ← wąskie gardła, ryzyko
│   ├── simulation.json   ← scenariusze, agenci, wyniki
│   ├── reports.json      ← raporty, PDF, share
│   ├── billing.json      ← plany, płatności, faktury
│   └── auth.json         ← login, rejestracja, konto
└── en/
    └── (identyczna struktura kluczy, naturalne EN tłumaczenia)
```

**Reguły i18n — OBOWIĄZKOWE dla Claude Code:**
- Zero hardkodowanych tekstów w komponentach .vue — wyłącznie `$t('klucz')`
- Klucze opisują funkcję, nie treść: `simulation.run_button` nie `uruchom_symulacje`
- Terminologia branżowa EN bez tłumaczenia: AIS, VLCC, chokepoint, bulk carrier, LNG, ETA, MMSI
- Daty i liczby przez `Intl.DateTimeFormat` / `Intl.NumberFormat` z aktualnym locale
- Pluralizacja przez vue-i18n syntax: `{count} vessel | {count} vessels`
- hreflang tagi automatycznie na każdej stronie przez `usePageMeta()` composable
- x-default hreflang wskazuje na /en (target: rynek globalny)

**Angielskie tłumaczenia — zasady tonu:**
Pisz naturalnie (native English), nie tłumacz dosłownie z polskiego.
- "Wąskie gardła" → "Bottlenecks"
- "Uruchom symulację" → "Run simulation"  
- "Zmień plan" → "Upgrade plan"
- "Ostatnia aktywność" → "Last seen"
- "Pobierz raport" → "Download report"

## Frontend rules

**All UI text must use `$t('key')` from vue-i18n.** Never hardcode Polish or English strings in `.vue` files. Every visible text — labels, buttons, tooltips, error messages, placeholders — must come from `locales/pl/*.json` or `locales/en/*.json`.

**All API calls go through `frontend/src/api/` typed client.** Never use raw `fetch`
or `axios` in components. The API client is generated from `openapi.yaml`.

**State management:** Pinia stores for: `useAuthStore`, `useMapStore`,
`useCommoditiesStore`, `useAlertsStore`, `useSimulationStore`.

**WebSocket / SSE:** Live data (vessel positions, alert feed) uses SSE from backend.
Connect in the relevant Pinia store, not in components.

**Mapbox GL JS:** Vessel positions rendered with Deck.gl `ScatterplotLayer` for
performance. Never add more than 3 custom layers to the map simultaneously — perf degrades.

**Error handling:** Every API call must handle 401 (redirect to login), 403 (show plan
upgrade modal), 429 (show rate limit toast), 500 (show generic error toast).

---

## Testing rules

**Backend:** pytest + httpx for API tests. Every new endpoint needs at minimum:
- 1 test for success case
- 1 test for auth failure (no token)
- 1 test for plan limit (wrong plan)

**Frontend:** Vitest + Vue Test Utils. Test stores, not components.

**Run tests:** `docker compose exec backend pytest` and `docker compose exec frontend npm test`

---

## Deployment

**Environments:** `local` (docker-compose.yml) → `staging` (same VPS, different port) →
`production` (Hetzner CPX31, docker-compose.prod.yml)

**Deploy process:**
1. Push to `main` branch
2. GitHub Actions: lint → test → build Docker image → push to GHCR
3. SSH to Hetzner → `docker compose pull && docker compose up -d`

**Database migrations run automatically on deploy** via entrypoint script before
FastAPI starts.

**Never run migrations manually in production** unless you know exactly what you're doing.

---

## Backup strategy

Daily automated backups run via the `backup` service in docker-compose.prod.yml:
- pg_dump to Hetzner Object Storage or Backblaze B2 every day at 03:00 UTC
- 7-day rolling retention
- Backup script: `infra/backup.sh`
- Verify backups monthly: `docker compose exec backup /backup.sh --verify`

**Setup on first deploy:**
```bash
# Add to .env.prod:
BACKUP_S3_BUCKET=supplyshock-backups
BACKUP_S3_ENDPOINT=https://your-region.your-provider.com
BACKUP_S3_KEY=xxx
BACKUP_S3_SECRET=xxx
```

---

## GDPR / Legal requirements

SupplyShock collects email addresses and usage data from EU users. Required:

1. **DELETE /api/v1/auth/me endpoint** — deletes user account + all associated data
   (simulations, reports, api_keys, subscriptions). Defined in openapi.yaml.
2. **Privacy policy page** at /privacy — generated via Iubenda (~€29/yr) or written manually.
3. **Cookie consent banner** — only needed if you add analytics (PostHog, Mixpanel).
   Clerk and Stripe set their own cookies — document these in privacy policy.
4. **Data retention** — vessel_positions: 90 days, alert_events: 1 year (set in schema.sql).
   User data: keep until deletion requested.

**Free users who delete their account:** anonymize email, keep simulation data
for analytics but strip user_id (set to NULL with ON DELETE SET NULL).

## Claude Code instructions

When starting a new session:
1. Read this file
2. Read `openapi.yaml` for any endpoint you're about to build
3. Read `schema.sql` for any database table you're about to use
4. For simulation work: read `OASIS_MODIFICATIONS.md` before touching `oasis_fork/`
5. Check the relevant GitHub Issue for acceptance criteria before writing code
6. Run tests after every change: `docker compose exec backend pytest -x`

When creating a new endpoint:
1. Add it to `openapi.yaml` first
2. Create Pydantic request/response models
3. Implement the endpoint
4. Write tests
5. Update this file if you add new conventions

When you're unsure about something: stop and ask rather than guess. A wrong
architecture decision is much more expensive than a 5-minute clarification.
