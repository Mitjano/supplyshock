# SupplyShock — GitHub Issues
# Skopiuj każdy blok jako osobny Issue na GitHub
# Milestone → Labels → Title → Body

---

## MILESTONE 0 — Fundament (przed Fazą 1)
> Cel: repo działa lokalnie, auth skonfigurowany, baza gotowa
> Czas: 2–3 dni
> Blokuje: wszystkie pozostałe Issues

---

### Issue #1
**Title:** `[M0] Initialize repo structure and verify docker-compose works`
**Labels:** `milestone-0` `infrastructure` `priority-critical`

**Cel:** Zainicjalizować strukturę projektu tak żeby `docker compose up -d` działało i wszystkie serwisy były healthy.

**Acceptance criteria:**
- [ ] Repo ma strukturę katalogów zgodną z CLAUDE.md (backend/, frontend/, infra/)
- [ ] `docker compose up -d` uruchamia wszystkie serwisy bez błędów
- [ ] `docker compose ps` pokazuje db, redis, backend, celery, frontend jako healthy
- [ ] `docker compose exec backend pytest` zwraca "no tests found" (nie błąd)
- [ ] `http://localhost:8000/docs` otwiera Swagger UI
- [ ] `http://localhost:5173` otwiera Vue app (nawet pustą)

**Pliki do stworzenia:**
- `backend/Dockerfile`
- `backend/main.py` (minimalny FastAPI app)
- `backend/requirements.txt`
- `backend/migrations/alembic.ini`
- `backend/migrations/env.py`
- `frontend/Dockerfile`
- `frontend/package.json` (Vue 3 + Vite)
- `frontend/index.html`
- `frontend/src/main.ts`

**Uwagi dla Claude Code:**
Czytaj CLAUDE.md sekcja "Tech stack" i "Directory structure". Backend Dockerfile musi uruchamiać `alembic upgrade head` przed `uvicorn`. Frontend to Vue 3 + Vite + TypeScript + Pinia + Vue Router.

---

### Issue #2
**Title:** `[M0] Create .gitignore and verify no secrets can be committed`
**Labels:** `milestone-0` `security` `priority-critical`

**Cel:** Upewnić się że `.env` i sekrety nie mogą być przypadkowo scommitowane.

**Acceptance criteria:**
- [ ] `.gitignore` istnieje w root repo
- [ ] `git status` nie pokazuje `.env` jako untracked
- [ ] `git add .env` zwraca "The following paths are ignored"
- [ ] `.env.example` jest tracked i zawiera wszystkie wymagane zmienne z pustymi wartościami

**Pliki:** `.gitignore` już istnieje — zweryfikuj że działa poprawnie.

---

### Issue #3
**Title:** `[M0] Setup Alembic migrations — initial schema`
**Labels:** `milestone-0` `database` `priority-critical`

**Cel:** Alembic skonfigurowany, schema.sql zaimportowany jako initial migration.

**Acceptance criteria:**
- [ ] `docker compose exec backend alembic upgrade head` wykonuje się bez błędów
- [ ] Wszystkie tabele z schema.sql istnieją w bazie po migracji
- [ ] `docker compose exec backend alembic current` pokazuje aktualną wersję
- [ ] Nowa migracja generuje się poprawnie: `alembic revision --autogenerate -m "test"`
- [ ] TimescaleDB hypertables są aktywne: `SELECT * FROM timescaledb_information.hypertables;` zwraca 4 wiersze

**Uwagi dla Claude Code:**
Alembic używa `DATABASE_URL_SYNC` (psycopg2), nie `DATABASE_URL` (asyncpg). Patrz sekcja "Alembic migrations" w CLAUDE.md. Initial migration powinna odzwierciedlać schema.sql — możesz ją napisać ręcznie zamiast autogenerate żeby mieć pełną kontrolę.

---

### Issue #4
**Title:** `[M0] Integrate Clerk auth — JWT verification middleware`
**Labels:** `milestone-0` `auth` `priority-critical`

**Cel:** Clerk JWT weryfikowany na każdym chronionym endpoincie. Google + email OAuth działają.

**Acceptance criteria:**
- [ ] `GET /api/v1/auth/me` bez tokenu zwraca 401
- [ ] `GET /api/v1/auth/me` z ważnym Clerk JWT zwraca dane usera
- [ ] Middleware w `backend/middleware/auth.py` weryfikuje podpis przez Clerk JWKS
- [ ] `POST /api/v1/auth/sync` tworzy/aktualizuje usera w tabeli `users`
- [ ] Frontend ma działający login przez Google i email (Clerk komponenty)
- [ ] Po zalogowaniu token jest dołączany do każdego requesta API

**Pliki do stworzenia:**
- `backend/auth/clerk.py`
- `backend/middleware/auth.py`
- `frontend/src/stores/useAuthStore.ts`
- `frontend/src/views/LoginView.vue`

**Uwagi dla Claude Code:**
Patrz sekcja "Auth rules" w CLAUDE.md. Używaj biblioteki `clerk-backend-api` lub weryfikuj JWT manualnie przez JWKS endpoint. Token z Clerk zawiera `sub` (clerk_user_id) i `email`.

---

### Issue #5
**Title:** `[M0] Implement plan-based RBAC middleware`
**Labels:** `milestone-0` `auth` `priority-high`

**Cel:** Dekoratory sprawdzające plan usera działają na endpointach.

**Acceptance criteria:**
- [ ] `@require_plan("pro")` na endpoincie blokuje Free usera z 403
- [ ] `@require_plan("pro")` przepuszcza Pro/Business/Enterprise usera
- [ ] `@check_simulation_limit` sprawdza `SELECT COUNT(*) WHERE created_at >= date_trunc('month', NOW())`
- [ ] Free user po 3 symulacjach w miesiącu dostaje 403 z kodem `SIMULATION_LIMIT_REACHED`
- [ ] Testy: test_rbac_free_blocked, test_rbac_pro_allowed, test_simulation_limit

**Pliki do stworzenia:**
- `backend/auth/rbac.py`
- `backend/tests/test_rbac.py`

---

### Issue #6
**Title:** `[M0] Implement rate limiting middleware`
**Labels:** `milestone-0` `security` `priority-high`

**Cel:** Rate limiting per plan per endpoint category działa przez Redis.

**Acceptance criteria:**
- [ ] Free user: po przekroczeniu limitu dostaje 429 z `Retry-After` headerem
- [ ] Redis klucz format: `rl:{user_id}:{endpoint_group}:{YYYYMMDD}`
- [ ] Endpoint groups: `simulation`, `report`, `api_calls`
- [ ] Limity zgodne z tabelą w CLAUDE.md (Free: 3 sim/mo, Pro: 50 sim/mo etc.)
- [ ] Test: test_rate_limit_429_after_exceeded

**Pliki do stworzenia:**
- `backend/middleware/rate_limit.py`
- `backend/tests/test_rate_limit.py`

---

## MILESTONE 1 — Faza 1: Live Map MVP
> Cel: mapa z żywymi statkami, portami, przepływami surowców — demo gotowe do GitHub launch
> Czas: 3 tygodnie
> Dependency: Milestone 0 complete

---

### Issue #7
**Title:** `[M1] AIS ingestion — connect aisstream.io WebSocket`
**Labels:** `milestone-1` `backend` `data-ingestion` `priority-critical`

**Cel:** Pozycje statków z aisstream.io zapisują się do TimescaleDB co kilka sekund.

**Acceptance criteria:**
- [ ] `backend/ingestion/ais_stream.py` łączy się z `wss://stream.aisstream.io/v0/stream`
- [ ] Parsuje AIS message types: PositionReport (typ 1,2,3) i StandardClassBPositionReport (typ 18)
- [ ] Zapisuje do tabeli `vessel_positions` przez batch insert co 5 sekund (nie row-by-row)
- [ ] Automatyczne reconnect po rozłączeniu (exponential backoff: 1s, 2s, 4s, max 60s)
- [ ] Celery task `tasks.start_ais_stream` uruchamia consumer jako długo-żyjący task
- [ ] `SELECT COUNT(*) FROM vessel_positions WHERE time > NOW() - INTERVAL '1 minute'` zwraca > 0 po 2 minutach działania
- [ ] Logi: ile pozycji zapisano co minutę

**Pliki do stworzenia:**
- `backend/ingestion/ais_stream.py`
- `backend/simulation/tasks.py` (dodaj task start_ais_stream)

---

### Issue #8
**Title:** `[M1] GET /api/v1/vessels — live vessel positions endpoint`
**Labels:** `milestone-1` `backend` `api` `priority-critical`

**Cel:** Endpoint zwracający aktualne pozycje statków dla viewport mapy.

**Acceptance criteria:**
- [ ] `GET /api/v1/vessels?bbox=-10,35,40,60&limit=500` zwraca pozycje w bbox
- [ ] Używa materialized view `latest_vessel_positions` (nie skanuje całej hypertable)
- [ ] Odpowiedź < 200ms dla bbox obejmującego Europę
- [ ] Zwraca format zgodny z openapi.yaml schema VesselPosition
- [ ] Parametr `vessel_type` filtruje po typie statku
- [ ] Test: test_vessels_returns_bbox_filtered, test_vessels_response_time

**Pliki do stworzenia:**
- `backend/api/v1/vessels.py`
- `backend/tests/test_vessels.py`

**Uwagi:** Refreshuj `latest_vessel_positions` materialized view co 30s przez Celery Beat task.

---

### Issue #9
**Title:** `[M1] GET /api/v1/vessels/{mmsi} — vessel detail`
**Labels:** `milestone-1` `backend` `api` `priority-high`

**Cel:** Pełne dane statku po kliknięciu na mapie.

**Acceptance criteria:**
- [ ] `GET /api/v1/vessels/123456789` zwraca pełne dane z ostatniej pozycji
- [ ] Zawiera: mmsi, imo, vessel_name, vessel_type, latitude, longitude, speed_knots, course, destination, eta, draught, flag_country, cargo_type, time
- [ ] 404 jeśli statek nie był widziany w ostatnich 2 godzinach
- [ ] Test: test_vessel_detail_found, test_vessel_detail_404

---

### Issue #10
**Title:** `[M1] GET /api/v1/vessels/{mmsi}/trail — vessel trail`
**Labels:** `milestone-1` `backend` `api` `priority-medium`

**Cel:** Historia trasy statku dla animacji na mapie.

**Acceptance criteria:**
- [ ] `GET /api/v1/vessels/123456789/trail?hours=24` zwraca pozycje z ostatnich 24h
- [ ] Posortowane chronologicznie (najstarsza pierwsza)
- [ ] Max `hours=168` (7 dni)
- [ ] Odpowiedź < 500ms nawet dla 168h
- [ ] Test: test_vessel_trail_sorted, test_vessel_trail_max_hours

---

### Issue #11
**Title:** `[M1] Import World Port Index — seed ports table`
**Labels:** `milestone-1` `backend` `database` `priority-critical`

**Cel:** 3500+ portów z NOAA WPI zaimportowanych do bazy i dostępnych przez API.

**Acceptance criteria:**
- [ ] Script `backend/scripts/seed_ports.py` importuje WPI CSV do tabeli `ports`
- [ ] `SELECT COUNT(*) FROM ports` zwraca > 3000
- [ ] `GET /api/v1/ports?is_major=true` zwraca porty z `is_major=true`
- [ ] `GET /api/v1/ports?bbox=-10,35,40,60` zwraca porty w regionie
- [ ] 25 bottleneck nodes z schema.sql seed są w tabeli `bottleneck_nodes`

**Pliki do stworzenia:**
- `backend/scripts/seed_ports.py`
- `backend/api/v1/ports.py`
- Pobierz WPI CSV z: https://msi.nga.mil/api/publications/download?key=16694622/SFH00000/UpdatedPub150.csv

---

### Issue #12
**Title:** `[M1] UN Comtrade — seed trade flows for top 5 commodities`
**Labels:** `milestone-1` `backend` `data-ingestion` `priority-critical`

**Cel:** Przepływy handlowe dla crude_oil, coal, iron_ore, copper, lng jako linie na mapie.

**Acceptance criteria:**
- [ ] Script `backend/scripts/seed_trade_flows.py` pobiera dane z UN Comtrade API
- [ ] Top 20 tras per surowiec (największe wolumeny) zapisane w `trade_flows`
- [ ] `GET /api/v1/commodities/flows?commodity=coal` zwraca GeoJSON FeatureCollection
- [ ] Każda feature ma properties: origin, destination, volume_mt, value_usd, commodity
- [ ] Geometry to LineString między origin_port i destination_port

**Pliki do stworzenia:**
- `backend/scripts/seed_trade_flows.py`
- `backend/api/v1/commodities.py` (endpoint /flows)

---

### Issue #13
**Title:** `[M1] Frontend — live map with vessels, ports, trade flows`
**Labels:** `milestone-1` `frontend` `priority-critical`

**Cel:** Interaktywna mapa MapLibre GL JS z żywymi statkami, portami i liniami przepływów.

**Acceptance criteria:**
- [ ] MapLibre GL JS z Deck.gl ScatterplotLayer renderuje pozycje statków (update co 30s)
- [ ] Statki kolorowane według vessel_type
- [ ] Kliknięcie na statek → popup z danymi z GET /api/v1/vessels/{mmsi}
- [ ] Porty renderowane jako punkty, kolorowane według commodity
- [ ] Przepływy surowców jako linie: grubość = volume_mt, kolor = commodity type
- [ ] Legenda po lewej: kolory surowców
- [ ] Filtry: vessel_type, commodity
- [ ] Mapa działa płynnie przy 5000+ statków

**Pliki do stworzenia:**
- `frontend/src/views/MapView.vue`
- `frontend/src/stores/useMapStore.ts`
- `frontend/src/components/map/VesselPopup.vue`
- `frontend/src/components/map/MapLegend.vue`
- `frontend/src/components/map/MapFilters.vue`

---

### Issue #14
**Title:** `[M1] Frontend — right panel: chokepoints, alerts, flows tabs`
**Labels:** `milestone-1` `frontend` `priority-high`

**Cel:** Panel po prawej stronie mapy z 3 zakładkami.

**Acceptance criteria:**
- [ ] Tab "Chokepoints": lista 7 krytycznych cieśnin z live vessel_count i risk_level
- [ ] Tab "Alerts": ostatnie 10 alertów z GET /api/v1/alerts (placeholder na tym etapie)
- [ ] Tab "Flows": tabela top 6 aktywnych tras surowcowych
- [ ] Kliknięcie na cieśninę podświetla ją na mapie
- [ ] Panel responsywny, nie blokuje mapy na małych ekranach

---

### Issue #15
**Title:** `[M1] Frontend — live feed panel (SSE alerts)`
**Labels:** `milestone-1` `frontend` `priority-medium`

**Cel:** Live feed eventów widoczny jako nakładka lub boczny panel.

**Acceptance criteria:**
- [ ] SSE connection do `GET /api/v1/alerts/stream`
- [ ] Nowe eventy pojawiają się bez refresh strony
- [ ] Filtrowanie: All / Alerts / AIS / Price / News
- [ ] Ticker cen surowców scrollujący na górze
- [ ] Liczniki: vessels tracked, active alerts, events today

**Uwagi:** Backend endpoint /alerts/stream może na tym etapie zwracać mock eventy co 30s. Prawdziwe dane GDELT dodasz w Milestone 2.

---

### Issue #16
**Title:** `[M1] GitHub release v0.1.0 — demo launch`
**Labels:** `milestone-1` `launch` `priority-critical`

**Cel:** Projekt gotowy do launchu na GitHub Trending.

**Acceptance criteria:**
- [ ] README.md z: hero GIF z animacją mapy, jednozdaniowy pitch, live demo link, quick start (3 komendy), screenshots mapy i dashboardu
- [ ] GitHub Actions CI: lint (ruff + eslint) → test → build
- [ ] `docker compose up -d` działa po `git clone` z wypełnionym `.env`
- [ ] Live demo dostępne pod publicznym URL (Hetzner VPS)
- [ ] Release tag v0.1.0 na GitHubie

**Pliki do stworzenia:**
- `README.md`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

---

## MILESTONE 2 — Faza 2: Commodity + Alerts
> Cel: dashboard surowców, system alertów GDELT+AIS, billing Stripe
> Czas: 4 tygodnie
> Dependency: Milestone 1 complete

---

### Issue #17
**Title:** `[M2] EIA + Quandl price ingestion — commodity_prices hypertable`
**Labels:** `milestone-2` `backend` `data-ingestion` `priority-critical`

**Cel:** Ceny 10 surowców aktualizowane automatycznie w TimescaleDB.

**Acceptance criteria:**
- [ ] `backend/ingestion/eia.py` pobiera dane EIA co 6h: crude_oil (WTI, Brent), lng (Henry Hub), coal (API2 proxy)
- [ ] `backend/ingestion/prices.py` pobiera z Quandl/Nasdaq Data Link: copper (LME), iron_ore, aluminium, nickel, wheat, soybeans
- [ ] Celery Beat schedule: EIA co 6h, Quandl co 1h
- [ ] `GET /api/v1/commodities/prices` zwraca najnowszą cenę per commodity/benchmark
- [ ] `GET /api/v1/commodities/prices/{commodity}/history?interval=1d&from=2026-01-01` zwraca OHLC (openapi.yaml: `/commodities/prices/{commodity}/history`)
- [ ] Test: test_prices_returns_latest, test_price_history_interval

**Pliki do stworzenia:**
- `backend/ingestion/eia.py`
- `backend/ingestion/prices.py`
- Rozszerz `backend/api/v1/commodities.py`

---

### Issue #18
**Title:** `[M2] GDELT news watcher — alert generation`
**Labels:** `milestone-2` `backend` `data-ingestion` `priority-critical`

**Cel:** GDELT monitoruje newsy co 15 minut i generuje alerty powiązane z surowcami.

**Acceptance criteria:**
- [ ] `backend/ingestion/gdelt.py` polluje GDELT GKG API co 15 minut
- [ ] Klasyfikuje eventy według: commodity (regex na nazwach regionów/produktów), severity (GDELT tone score → info/warning/critical)
- [ ] Zapisuje do `alert_events` tylko nowe eventy (dedup po source_url)
- [ ] `GET /api/v1/alerts?type=news_event&severity=critical` zwraca alerty GDELT
- [ ] Test: test_gdelt_dedup, test_gdelt_classification

**Pliki do stworzenia:**
- `backend/ingestion/gdelt.py`
- `backend/api/v1/alerts.py`

---

### Issue #19
**Title:** `[M2] AIS anomaly detection — vessel congestion alerts`
**Labels:** `milestone-2` `backend` `priority-high`

**Cel:** System automatycznie wykrywa nieoczekiwany wzrost liczby statków przy cieśninach.

**Acceptance criteria:**
- [ ] Celery task co 30 minut: dla każdego bottleneck_node zlicz statki w promieniu 50km
- [ ] Zapisuj do `chokepoint_status`: vessel_count, avg_speed, congestion_index
- [ ] Jeśli vessel_count > mean + 2*std (z ostatnich 30 dni) → stwórz alert AIS_ANOMALY
- [ ] `GET /api/v1/bottlenecks/{slug}/status` zwraca aktualny status i historię 7 dni
- [ ] Test: test_anomaly_detection_triggers_alert

**Pliki do stworzenia:**
- Rozszerz `backend/simulation/tasks.py` (anomaly detection task)
- `backend/api/v1/bottlenecks.py`

---

### Issue #20
**Title:** `[M2] GET /api/v1/alerts/stream — SSE live feed`
**Labels:** `milestone-2` `backend` `api` `priority-high`

**Cel:** Server-Sent Events dla live alertów w frontendzie.

**Acceptance criteria:**
- [ ] `GET /api/v1/alerts/stream` utrzymuje połączenie SSE
- [ ] Nowy alert w `alert_events` → natychmiast wysyłany do wszystkich połączonych klientów przez Redis pub/sub
- [ ] Klient dostaje heartbeat co 30s żeby połączenie nie wygasło
- [ ] Automatyczne odłączenie po 1h (client może reconnectować)
- [ ] Test: test_sse_receives_new_alert

---

### Issue #21
**Title:** `[M2] Alert subscriptions — GET/POST/DELETE /api/v1/alert-subscriptions`
**Labels:** `milestone-2` `backend` `api` `priority-medium`

**Cel:** Użytkownik może subskrybować alerty dla konkretnych surowców/regionów.

**Acceptance criteria:**
- [ ] `GET /api/v1/alert-subscriptions` — lista subskrypcji usera
- [ ] `POST /api/v1/alert-subscriptions` — utwórz subskrypcję
- [ ] `DELETE /api/v1/alert-subscriptions/{id}` — usuń subskrypcję (openapi.yaml)
- [ ] CRUD zgodny z openapi.yaml schema dla `user_alert_subscriptions`
- [ ] Nowy alert matching subskrypcję → email przez Resend
- [ ] Test: test_subscription_creates, test_subscription_triggers_email

---

### Issue #22
**Title:** `[M2] Stripe billing — Checkout + webhooks`
**Labels:** `milestone-2` `billing` `priority-critical`

**Cel:** Użytkownik może kupić plan Pro lub Business. Webhook aktualizuje plan w Clerk i bazie.

**Acceptance criteria:**
- [ ] `POST /api/v1/billing/checkout` zwraca Stripe Checkout URL
- [ ] Po opłaceniu: `checkout.session.completed` webhook aktualizuje `users.plan` + Clerk metadata
- [ ] `invoice.payment_failed` → email ostrzegawczy przez Resend
- [ ] Po 3 nieudanych → downgrade do Free
- [ ] `customer.subscription.deleted` → natychmiastowy downgrade
- [ ] `POST /api/v1/billing/portal` zwraca Stripe Customer Portal URL
- [ ] Stripe webhook signature weryfikowana (STRIPE_WEBHOOK_SECRET)
- [ ] Test: test_webhook_signature_required, test_checkout_session_upgrades_plan

**Pliki do stworzenia:**
- `backend/webhooks/stripe.py`
- `backend/api/v1/billing.py`

---

### Issue #23
**Title:** `[M2] Transactional emails — Resend integration`
**Labels:** `milestone-2` `backend` `email` `priority-high`

**Cel:** System wysyła emaile transakcyjne przez Resend.

**Acceptance criteria:**
- [ ] Email weryfikacyjny po rejestracji
- [ ] Email resetowania hasła (obsługiwany przez Clerk, ale customizuj template)
- [ ] Email po pomyślnym upgrade planu ("Witaj w Pro!")
- [ ] Email przy payment_failed ("Płatność nieudana")
- [ ] Email z alertem krytycznym (jeśli user ma notify_email=true)
- [ ] Wszystkie szablony w `backend/email/templates/` jako Jinja2 HTML templates

**Pliki do stworzenia:**
- `backend/email/resend.py`
- `backend/email/templates/welcome_pro.html`
- `backend/email/templates/payment_failed.html`
- `backend/email/templates/critical_alert.html`

---

### Issue #24
**Title:** `[M2] Frontend — commodity dashboard`
**Labels:** `milestone-2` `frontend` `priority-high`

**Cel:** Dashboard z cenami surowców, wykresami historycznymi i tabelą przepływów.

**Acceptance criteria:**
- [ ] Grid kart cenowych: 8 surowców z ceną, zmianą 24h i mini sparkline
- [ ] Kliknięcie karty → duży wykres historyczny z timeframe 1D/1W/1M/3M/1Y
- [ ] Tabela Physical Flows: top trasy per wybrany surowiec
- [ ] Filtry: All / Energy / Metals / Agriculture
- [ ] Dane real-time z GET /api/v1/commodities/prices (polling co 60s)

---

### Issue #25
**Title:** `[M2] Frontend — bottleneck monitor view`
**Labels:** `milestone-2` `frontend` `priority-high`

**Cel:** Widok wąskich gardeł z listą, risk barami i panelem szczegółów.

**Acceptance criteria:**
- [ ] Lista 40 bottleneck nodes z: nazwa, commodity tags, risk bar, risk level badge
- [ ] Kliknięcie → panel szczegółów: stats (throughput, status, risk index), dependency graph SVG, historia incydentów
- [ ] Przycisk "Run Simulation" przenosi do widoku symulacji z pre-wypełnionym node
- [ ] Dane z GET /api/v1/bottlenecks i GET /api/v1/bottlenecks/{slug}

---

## MILESTONE 3 — Faza 3: Simulation Engine
> Cel: OASIS commodity fork + multi-agent symulacje + raporty PDF
> Czas: 5 tygodni (fork 1 tydzień + simulation infra 4 tygodnie)
> Dependency: Milestone 2 complete
> WAŻNE: Issue #26 musi być CAŁKOWICIE zamknięty (wszystkie etapy A-E) przed Issues #27–#31

---

### Issue #26
**Title:** `[M3] OASIS commodity fork — implement all source modifications`
**Labels:** `milestone-3` `simulation` `priority-critical`

**Cel:** Zaimplementować kompletny commodity fork OASIS według audytu kodu źródłowego. Fork jest prerequisites dla Issues #27–#31 — żaden z nich nie może się zacząć bez zamkniętego #26.

**Kontekst (czytaj przed kodem):**
OASIS zakłada social media semantykę. Nasz fork podmienia semantykę przy minimalnej ingerencji w logikę core. Kluczowy pattern w platform.py L148: `getattr(self, action.value)` — platforma wywołuje metodę po nazwie z ActionType enum. Dodanie nowej akcji = dodaj enum value + async method o tej samej nazwie. Zero magii.

**ETAP A — Schema (dzień 1)**

Acceptance criteria:
- [ ] `backend/simulation/oasis_fork/social_platform/schema/trade.sql` stworzony
- [ ] `backend/simulation/oasis_fork/social_platform/schema/market_state.sql` stworzony
- [ ] `backend/simulation/oasis_fork/social_platform/schema/vessel_decision.sql` stworzony
- [ ] `database.py` ładuje te 3 pliki w `create_db()` (graceful — `if osp.exists(path)`)
- [ ] Test: `create_db()` tworzy tabele `trade`, `market_state`, `vessel_decision` bez błędu
- [ ] Stare tabele OASIS (user, post, trace, etc.) nadal działają — backwards compatible

Pliki:
- `schema/trade.sql`: `trade_id, agent_id, commodity, action, volume_mt, price_view, created_at`
- `schema/market_state.sql`: `state_id, commodity, agent_id, price_view, confidence, timestep, created_at`
- `schema/vessel_decision.sql`: `decision_id, agent_id, mmsi, original_port, new_port, reason, created_at`

**ETAP B — ActionType + Platform handlers (dzień 1)**

Acceptance criteria:
- [ ] `typing.py` ma 5 nowych ActionType: `SUBMIT_TRADE`, `REROUTE_VESSEL`, `UPDATE_PRICE_VIEW`, `IMPOSE_MEASURE`, `ACTIVATE_INVENTORY`
- [ ] `DefaultPlatformType` ma nowy wariant `COMMODITY = "commodity"`
- [ ] `platform.py` ma 5 async methods: `submit_trade`, `reroute_vessel`, `update_price_view`, `impose_measure`, `activate_inventory`
- [ ] KAŻDA metoda ma max 3 parametry: `self, agent_id, message_tuple` (hard constraint w platform.py L155)
- [ ] KAŻDA metoda wywołuje `self.pl_utils._record_trace()` — pełny audit trail w SQLite
- [ ] `env.py` obsługuje `DefaultPlatformType.COMMODITY` w `OasisEnv.__init__`
- [ ] Test: `ManualAction(ActionType.SUBMIT_TRADE, {"commodity": "coal", "action": "buy", "volume_mt": 500000, "price_view": 125.0})` wykonuje się bez błędu

Uwaga krytyczna dla Claude Code: metody platform muszą pakować dane w tuple bo platform.py obsługuje max 2 parametry poza `self`. Wzorzec: `action_message: tuple` jako drugi parametr, `commodity, action, volume, price = action_message` wewnątrz.

**ETAP C — CommodityAgentInfo + CommodityEnvironment (dzień 2)**

Acceptance criteria:
- [ ] `config/user.py` ma dataclass `CommodityAgentInfo` z polami: `user_name, agent_type, commodity, description, inventory_days, risk_tolerance, region`
- [ ] `CommodityAgentInfo.to_system_message()` zwraca prompt bez słów "Twitter", "Reddit", "posts", "social media"
- [ ] `agent_environment.py` ma subclass `CommodityEnvironment(SocialEnvironment)` z nadpisaną `to_text_prompt()`
- [ ] `CommodityEnvironment.to_text_prompt()` formatuje "posty" jako `[EVENT] {content}` market intelligence zamiast social feed
- [ ] `CommodityEnvironment._get_market_state()` czyta z tabeli `market_state` aktualny consensus
- [ ] `agent.py` używa `CommodityEnvironment` jeśli `isinstance(user_info, CommodityAgentInfo)`, `SocialEnvironment` w przeciwnym razie
- [ ] Test: agent z `CommodityAgentInfo` dostaje system prompt zawierający słowa "commodity", "trading", "market"

**ETAP D — Moduł commodity/ (dzień 2–3)**

Acceptance criteria:
- [ ] `backend/simulation/oasis_fork/commodity/__init__.py` stworzony
- [ ] `commodity/toolkits.py` ma funkcje z kompletnym docstring i type annotations (wymagane przez CAMEL FunctionTool): `get_commodity_price(commodity: str) -> dict`, `get_port_congestion(port_slug: str) -> dict`, `get_trade_flow(commodity: str, origin: str, destination: str) -> dict`
- [ ] `commodity/toolkits.py` ma `COMMODITY_TOOLS: list[FunctionTool]` — gotowa lista do przekazania agentom
- [ ] `commodity/agents.py` ma fabryki: `make_coal_trader(agent_id, graph, model, region)`, `make_bulk_shipper(agent_id, graph, model)`, `make_government_agent(agent_id, graph, model, country)`
- [ ] `commodity/market.py` ma `compute_consensus_price(commodity, db_path) -> float` — agreguje `AVG(price_view)` z market_state
- [ ] Test: `make_coal_trader(0, graph, mock_model)` zwraca `SocialAgent` z system promptem commodity

**ETAP E — POC Newcastle flood (dzień 3)**

Acceptance criteria:
- [ ] `backend/simulation/poc_newcastle.py` uruchamia się bez błędu: `python poc_newcastle.py`
- [ ] Konfiguracja: 100 agentów (10 LLM z Haiku + 90 ManualAction DO_NOTHING), 5 kroków
- [ ] Seed event jako `ManualAction(CREATE_POST, {"content": "BREAKING: Hunter Valley railway flooded — coal exports disrupted 3 weeks, 11M t monthly deficit"})` wstrzyknięty w krok 0
- [ ] Po 5 krokach: `SELECT COUNT(*) FROM trade WHERE action IN ('buy_spot','buy_futures')` zwraca > 6 (≥60% LLM agentów reaguje)
- [ ] Średnia `price_view` z tabeli `market_state` > 118.40 (baseline) — agenci widzą wzrost
- [ ] Koszt LLM < $0.50 (10 agentów × 5 kroków × ~400 tokenów × Haiku $0.25/1M)
- [ ] Czas wykonania < 3 minuty
- [ ] Wyniki heterogeniczne: co najmniej 2 różne wartości `action` w tabeli `trade`
- [ ] Jeśli którekolwiek kryterium nie jest spełnione: debuguj prompt agenta i opis w `CommodityAgentInfo` (nie sam OASIS) — daj sobie 3 iteracje

**Pliki do stworzenia/modyfikacji:**

OASIS fork location: `backend/simulation/oasis_fork/` (nie modyfikuj zainstalowanego pakietu — pracuj na lokalnej kopii)

```
backend/simulation/oasis_fork/
├── social_platform/
│   ├── typing.py              ← MODYFIKACJA: +5 ActionType, +COMMODITY platform
│   ├── platform.py            ← MODYFIKACJA: +5 async handlers
│   ├── database.py            ← MODYFIKACJA: ładuj commodity schemas
│   └── schema/
│       ├── trade.sql          ← NOWY
│       ├── market_state.sql   ← NOWY
│       └── vessel_decision.sql ← NOWY
├── social_agent/
│   ├── agent.py               ← MODYFIKACJA: CommodityAgentInfo routing
│   └── agent_environment.py   ← MODYFIKACJA: +CommodityEnvironment
├── social_platform/config/
│   └── user.py                ← MODYFIKACJA: +CommodityAgentInfo dataclass
├── environment/
│   └── env.py                 ← MODYFIKACJA: +COMMODITY w OasisEnv.__init__
└── commodity/                 ← NOWY MODUŁ
    ├── __init__.py
    ├── toolkits.py
    ├── agents.py
    └── market.py

backend/simulation/poc_newcastle.py  ← NOWY (POC script)
```

**Uwagi dla Claude Code:**
1. Zainstaluj oryginalny OASIS przez `pip install camel-oasis` tylko do przeczytania — fork kopiuj do `oasis_fork/`
2. Platform ma hard constraint: max 3 parametry per handler (L155 w platform.py) — używaj tuple dla message
3. FunctionTool wymaga pełnego docstring z Args i Returns — bez tego CAMEL nie zbuduje tool schema
4. `CommodityEnvironment.to_text_prompt()` musi zwracać string (nie coroutine) — patrz jak robi to `SocialEnvironment`
5. Testuj każdy etap osobno zanim przejdziesz do następnego

---

---

### Issue #27
**Title:** `[M3] POST /api/v1/simulations — queue simulation as Celery task`
**Labels:** `milestone-3` `backend` `api` `simulation` `priority-critical`

**Cel:** Endpoint przyjmuje scenariusz, kolejkuje Celery task, zwraca job_id natychmiast.

**Acceptance criteria:**
- [ ] `POST /api/v1/simulations` z body zgodnym z SimulationParameters → zwraca 201 z simulation.id natychmiast (< 100ms)
- [ ] Rekord w `simulations` ma status=queued
- [ ] Celery task `run_simulation` pobiera zadanie, uruchamia OASIS, aktualizuje progress co 10 agentów
- [ ] Timeout 10 minut (task_time_limit)
- [ ] `@check_simulation_limit` blokuje Free usera po 3 symulacjach w miesiącu
- [ ] Test: test_simulation_queued, test_simulation_limit_blocked

**Pliki do stworzenia:**
- Rozszerz `backend/api/v1/simulations.py`
- Rozszerz `backend/simulation/tasks.py` (run_simulation Celery task)
- `backend/simulation/engine.py` (OASIS orchestration — używa `oasis_fork/`)

**Uwaga dla Claude Code:** engine.py importuje z `backend/simulation/oasis_fork/` nie z zainstalowanego `oasis` pakietu. Dodaj `sys.path.insert(0, "backend/simulation")` lub skonfiguruj jako lokalny package.

---

### Issue #28
**Title:** `[M3] GET /api/v1/simulations/{id}/stream — SSE progress`
**Labels:** `milestone-3` `backend` `api` `priority-high`

**Cel:** Frontend otrzymuje progress symulacji w czasie rzeczywistym przez SSE.

**Acceptance criteria:**
- [ ] SSE stream wysyła eventy co 5 sekund: `{"progress": 45, "log": "t+12h: traders reacting..."}`
- [ ] Po zakończeniu: `{"status": "completed", "result": {...}}`
- [ ] Po błędzie: `{"status": "failed", "error": "timeout after 10 minutes"}`
- [ ] Klient może reconnectować (stateless — czyta aktualny stan z Redis)
- [ ] Test: test_simulation_stream_progress, test_simulation_stream_complete

---

### Issue #29
**Title:** `[M3] POST /api/v1/reports — generate PDF via Claude API`
**Labels:** `milestone-3` `backend` `api` `priority-high`

**Cel:** Raport PDF generowany przez Claude API z wyników symulacji.

**Acceptance criteria:**
- [ ] `POST /api/v1/reports` z simulation_id → kolejkuje Celery task
- [ ] Task wysyła wyniki symulacji do Claude API (claude-sonnet-4-6) z promptem do analizy
- [ ] Claude generuje narracyjny raport w języku angielskim: executive summary, price predictions, winners/losers, recommendations
- [ ] WeasyPrint konwertuje HTML → PDF
- [ ] PDF zapisywany lokalnie (dev) lub na Hetzner Object Storage (prod)
- [ ] `reports.pdf_url` ustawiony po zakończeniu
- [ ] Timeout 2 minuty
- [ ] Test: test_report_generates, test_report_pdf_accessible

**Pliki do stworzenia:**
- `backend/api/v1/reports.py`
- `backend/simulation/report_generator.py`

---

### Issue #30
**Title:** `[M3] POST /api/v1/reports/{id}/share — public share link`
**Labels:** `milestone-3` `backend` `api` `priority-medium`

**Cel:** Użytkownik może udostępnić raport publicznym linkiem.

**Acceptance criteria:**
- [ ] `POST /api/v1/reports/{id}/share` generuje `share_token` (32-znakowy random hex)
- [ ] `GET /api/v1/reports/shared/{token}` zwraca raport bez auth (public endpoint)
- [ ] `share_expires_at` ustawiony na now + expires_days
- [ ] Wygasły token zwraca 404
- [ ] Test: test_share_link_public_access, test_share_link_expired

---

### Issue #31
**Title:** `[M3] Frontend — simulation view with live progress`
**Labels:** `milestone-3` `frontend` `priority-critical`

**Cel:** UI do konfiguracji i uruchamiania symulacji z live progressem.

**Acceptance criteria:**
- [ ] Formularz konfiguracji: node (dropdown), event_type, description, duration_weeks, intensity, agents, horizon_days
- [ ] "Run Simulation" → POST /api/v1/simulations → progress bar przez SSE
- [ ] Live log agentów scrolluje podczas symulacji
- [ ] Po zakończeniu: price predictions grid, winners/losers, agent log
- [ ] Przycisk "Export PDF" → POST /api/v1/reports → download gdy gotowy
- [ ] Historia symulacji: lista poprzednich z GET /api/v1/simulations

---

## MILESTONE 4 — Faza 4: Monetyzacja
> Cel: user accounts, billing UI, API keys, production deploy
> Czas: 3 tygodnie
> Dependency: Milestone 3 complete

---

### Issue #32
**Title:** `[M4] API key management — generate/revoke keys`
**Labels:** `milestone-4` `backend` `api` `priority-high`

**Cel:** Pro+ użytkownicy mogą tworzyć i zarządzać kluczami API.

**Acceptance criteria:**
- [ ] `POST /api/v1/api-keys` generuje klucz (format: `sk_live_{32 random chars}`)
- [ ] Klucz haszowany SHA-256 przed zapisem — nigdy nie przechowywany plaintext
- [ ] Klucz pokazywany tylko raz w odpowiedzi (ApiKeyCreated schema)
- [ ] `GET /api/v1/api-keys` zwraca listę z key_prefix (nigdy pełny klucz)
- [ ] `DELETE /api/v1/api-keys/{id}` deaktywuje klucz
- [ ] API klucz akceptowany jako alternatywa dla JWT w headerze Authorization
- [ ] Użycie klucza aktualizuje `api_keys.last_used_at`
- [ ] Test: test_key_created_once, test_key_hash_not_plaintext, test_key_auth_works

---

### Issue #33
**Title:** `[M4] Frontend — settings page (billing, API keys, alerts, account)`
**Labels:** `milestone-4` `frontend` `priority-high`

**Cel:** Strona ustawień z 4 sekcjami.

**Acceptance criteria:**
- [ ] Tab "Billing": aktualny plan, daty, przycisk Upgrade (→ Checkout) lub Manage (→ Portal)
- [ ] Tab "API Keys": lista kluczy z last_used, formularz tworzenia, przycisk Revoke
- [ ] Tab "Alerts": lista subskrypcji alertów, formularz dodawania, przycisk Delete
- [ ] Tab "Account": email, avatar, przycisk "Delete account" (z potwierdzeniem)
- [ ] Delete account → DELETE /api/v1/auth/me → logout → redirect na homepage

---

### Issue #34
**Title:** `[M4] DELETE /api/v1/auth/me — GDPR account deletion`
**Labels:** `milestone-4` `backend` `api` `security` `priority-high`

**Cel:** Użytkownik może usunąć konto i wszystkie dane zgodnie z RODO.

**Acceptance criteria:**
- [ ] Endpoint usuwa: user, subscriptions, api_keys, simulations, reports, alert_subscriptions
- [ ] Anuluje aktywną subskrypcję Stripe przed usunięciem (jeśli istnieje)
- [ ] Usuwa użytkownika z Clerk
- [ ] Zwraca 204 po pomyślnym usunięciu
- [ ] Loguje do audit_log: `action: "account.deleted"`
- [ ] Test: test_account_deletion_removes_all_data, test_active_subscription_cancelled

---

### Issue #35
**Title:** `[M4] Production deploy — Hetzner VPS + Nginx + TLS`
**Labels:** `milestone-4` `infrastructure` `priority-critical`

**Cel:** Produkcyjny deployment na Hetzner z HTTPS, backupami i monitoringiem.

**Acceptance criteria:**
- [ ] `docker compose -f docker-compose.prod.yml up -d` działa na Hetzner CPX31
- [ ] HTTPS działa: `https://supplyshock.io` i `https://api.supplyshock.io`
- [ ] Let's Encrypt cert automatycznie odnawiany przez certbot service
- [ ] `infra/nginx.conf` ma wszystkie security headers z CLAUDE.md
- [ ] Backup service działa: pg_dump co 24h do object storage
- [ ] GitHub Actions deploy workflow: push → build → push GHCR → SSH deploy
- [ ] Health check endpoint: `GET /health` zwraca `{"status": "ok", "db": "ok", "redis": "ok"}`

**Pliki do stworzenia:**
- `infra/nginx.conf`
- `backend/api/health.py`
- `.github/workflows/deploy.yml`

---


### Issue #36
**Title:** `[M0] Setup Vue i18n — /pl and /en routing, locale detection, language switcher`
**Labels:** `milestone-0` `frontend` `infrastructure` `i18n` `priority-high`

**Cel:** Cała aplikacja obsługuje dwa języki (PL/EN) z prefiksem URL. Każdy string w UI pochodzi z pliku lokalizacyjnego — zero hardkodowanego tekstu w komponentach.

**Acceptance criteria:**
- [ ] `vue-i18n` zainstalowany i skonfigurowany w `frontend/src/i18n.ts`
- [ ] Router używa `/:locale(pl|en)` jako prefiks dla wszystkich tras
- [ ] `/` automatycznie wykrywa język przeglądarki i redirectuje do `/pl` lub `/en`
- [ ] Domyślny język dla nieznanych przeglądarek: `/en` (target globalny)
- [ ] Przełącznik `PL | EN` w navbar — zmiana podmienia prefiks URL i zapisuje w `localStorage`
- [ ] `hreflang` tagi generowane automatycznie przez `useHead()` na każdej stronie
- [ ] Pliki `locales/pl/*.json` i `locales/en/*.json` istnieją dla wszystkich 8 modułów
- [ ] Zero hardkodowanych polskich ani angielskich tekstów w komponentach `.vue`
- [ ] `npm run build` nie pokazuje ostrzeżeń o brakujących kluczach i18n
- [ ] Test: zmiana języka w navbar → URL zmienia się z `/pl/map` na `/en/map` i odwrotnie

**Pliki do stworzenia:**
- `frontend/src/i18n.ts` — konfiguracja vue-i18n, lazy loading per locale
- `frontend/src/router/index.ts` — zaktualizowany z `/:locale(pl|en)` prefixem
- `frontend/src/composables/useLocale.ts` — detect, switch, persist locale
- `frontend/src/layouts/LocaleLayout.vue` — guard sprawdzający locale param w URL
- `frontend/src/components/LocaleSwitcher.vue` — przełącznik PL | EN
- `frontend/src/composables/usePageMeta.ts` — hreflang + og:locale per strona
- `frontend/src/locales/pl/common.json` — nawigacja, przyciski, błędy, daty
- `frontend/src/locales/pl/map.json` — mapa, statki, cieśniny, popup
- `frontend/src/locales/pl/commodities.json` — surowce, ceny, przepływy, wykresy
- `frontend/src/locales/pl/bottlenecks.json` — wąskie gardła, ryzyko, incydenty
- `frontend/src/locales/pl/simulation.json` — scenariusze, agenci, wyniki, predykcje
- `frontend/src/locales/pl/reports.json` — raporty, PDF, share, historia
- `frontend/src/locales/pl/billing.json` — plany, płatności, limity, faktury
- `frontend/src/locales/pl/auth.json` — login, rejestracja, profil, konto, RODO
- `frontend/src/locales/en/*.json` — lustrzana struktura, naturalne EN (nie tłumaczenie mechaniczne)

**Uwagi dla Claude Code:**
- Klucze i18n opisują funkcję elementu, nie jego treść: `simulation.run_button` nie `uruchom`
- Terminologia branżowa w EN bez tłumaczenia: AIS, VLCC, chokepoint, bulk carrier, LNG, ETA, MMSI
- Daty i liczby przez `Intl.DateTimeFormat` i `Intl.NumberFormat` z locale — nie ręczne formatowanie
- Pluralizacja przez vue-i18n `{count} vessel | {count} vessels` — nie if/else w komponentach
- Angielskie tłumaczenia piszesz naturalnie (native tone), nie kalkulujesz z polskiego

---


### Issue #37
**Title:** `[M2] Onboarding flow — empty state, get started checklist, welcome email`
**Labels:** `milestone-2` `frontend` `backend` `email` `priority-high`

**Cel:** Nowy użytkownik po pierwszej rejestracji widzi wartość produktu w ciągu 2 minut — nie pustą mapę.

**Acceptance criteria:**
- [ ] Po pierwszej rejestracji (Clerk webhook `user.created`) → backend auto-tworzy rekord w `users` + wysyła email powitalny przez Resend
- [ ] Mapa przy pierwszym otwarciu pokazuje pre-loaded scenariusz: Newcastle coal port z aktualnym statusem i 3 statkami na redzie
- [ ] Panel "Get started" (checklist 3 kroków): ☐ Explore the map → ☐ Run your first simulation → ☐ Set up an alert
- [ ] Kliknięcie "Run your first simulation" → otwiera Simulation view z pre-wypełnionym scenariuszem Newcastle flood
- [ ] Po ukończeniu każdego kroku checklisty → zapisz w `users.onboarding_completed_steps` (JSONB)
- [ ] Checklist znika gdy wszystkie 3 kroki ukończone lub user kliknie "Dismiss"
- [ ] Email powitalny: nazwa produktu, co to jest, link do mapy, link do first simulation

**Pliki do stworzenia:**
- `frontend/src/components/OnboardingChecklist.vue`
- `backend/email/templates/welcome.tsx`
- Dodaj `onboarding_completed_steps JSONB` do tabeli `users` (Alembic migration)
- Dodaj Clerk webhook handler dla `user.created` event

**Uwagi dla Claude Code:**
Checklist pojawia się tylko gdy `onboarding_completed_steps` nie zawiera wszystkich 3 kluczy. Używaj `$t()` dla wszystkich tekstów. Pre-loaded scenariusz to hardkodowany przykład — nie wywołuj prawdziwej symulacji.

---

### Issue #38
**Title:** `[M4] Error monitoring — Sentry integration (backend + frontend + Celery)`
**Labels:** `milestone-4` `backend` `frontend` `infrastructure` `priority-high`

**Cel:** Wszystkie błędy w produkcji są automatycznie raportowane do Sentry — bez potrzeby patrzenia w logi żeby wiedzieć że coś padło.

**Acceptance criteria:**
- [ ] Sentry SDK zainstalowany w backend (sentry-sdk[fastapi]) i frontend (@sentry/vue)
- [ ] Wszystkie niezłapane wyjątki FastAPI → Sentry automatycznie
- [ ] Celery task failures → Sentry z pełnym traceback i task name
- [ ] Frontend JS errors → Sentry z Vue component name i route
- [ ] `SENTRY_DSN` z `.env` — brak DSN = Sentry wyłączony (dev nie raportuje)
- [ ] Performance tracing: FastAPI traces (sample rate 10%), Celery traces
- [ ] Alert Sentry: email do właściciela przy pierwszym wystąpieniu nowego błędu
- [ ] Test: celowo wywołaj błąd → sprawdź że pojawia się w Sentry dashboard

**Pliki do modyfikacji:**
- `backend/main.py` — inicjalizacja Sentry przy starcie
- `backend/simulation/tasks.py` — Celery Sentry integration
- `frontend/src/main.ts` — Sentry Vue plugin
- `.env.example` — SENTRY_DSN już jest (optional)

**Uwagi:** Sentry free tier: 5k errors/mies + 10k performance transactions — wystarczy do ~500 active users.

---

## Kolejność wykonania (dependency graph)

```
M0: #1 → #2 → #3 → #4 → #5 → #6 → #36 (i18n)
                                              ↓
M1: #7 → #8 → #9 → #10
    #11 → #12
    #13 → #14 → #15  (wszystkie komponenty używają $t() od razu)
    #16 (launch — wszystkie M1 complete)
                                              ↓
M2: #17 → #18 → #19 → #20 → #21
    #22 → #23
    #24 → #25
    #37 (onboarding — po #22 auth działa)
                                              ↓
M3: #26 (OASIS fork: etapy A→B→C→D→E, wszystkie muszą przejść)
         ↓
    #27 → #28 → #29 → #30 → #31
                                              ↓
M4: #32 → #33 → #34 → #35 → #38 (Sentry)
```

## GitHub Labels do stworzenia

```
milestone-0    (kolor: #e11d48)
milestone-1    (kolor: #7c3aed)
milestone-2    (kolor: #1d4ed8)
milestone-3    (kolor: #0369a1)
milestone-4    (kolor: #065f46)
priority-critical  (kolor: #dc2626)
priority-high      (kolor: #ea580c)
priority-medium    (kolor: #ca8a04)
infrastructure (kolor: #6b7280)
backend        (kolor: #2563eb)
frontend       (kolor: #7c3aed)
database       (kolor: #16a34a)
auth           (kolor: #dc2626)
security       (kolor: #dc2626)
api            (kolor: #0891b2)
data-ingestion (kolor: #0d9488)
simulation     (kolor: #7c3aed)
billing        (kolor: #16a34a)
email          (kolor: #6366f1)
launch         (kolor: #f59e0b)
i18n           (kolor: #0891b2)
oasis-fork     (kolor: #7c3aed)
onboarding     (kolor: #7c3aed)
monitoring     (kolor: #6b7280)

## Decyzja architektoniczna: MapLibre GL JS (zatwierdzona)
Używamy MapLibre GL JS — open-source fork Mapbox z identycznym API, $0 zawsze.
- npm: `maplibre-gl` (nie `mapbox-gl`)
- Nie wymaga tokena API (darmowe tile serwery lub self-hosted)
- Issue #13 i wszystkie komponenty mapowe używają MapLibre
```
