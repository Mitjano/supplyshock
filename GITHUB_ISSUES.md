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

voyage-intelligence (kolor: #0d9488)
predictive-analytics (kolor: #0891b2)
compliance     (kolor: #dc2626)
ai-chat        (kolor: #7c3aed)
export         (kolor: #16a34a)
```

## Decyzja architektoniczna: MapLibre GL JS (zatwierdzona)
Używamy MapLibre GL JS — open-source fork Mapbox z identycznym API, $0 zawsze.
- npm: `maplibre-gl` (nie `mapbox-gl`)
- Nie wymaga tokena API (darmowe tile serwery lub self-hosted)
- Issue #13 i wszystkie komponenty mapowe używają MapLibre

## Decyzja architektoniczna: AI Chat model (zatwierdzona)
- Główny model: **Gemini 2.5 Flash** ($0.30/1M input, $2.50/1M output, 1M context)
- Fallback: **Claude Haiku 4.5** ($1.00/$5.00, 200K context) dla złożonych analiz
- Szacowany koszt: ~$20-60/mies. przy 1000 zapytań/dzień

## Decyzja architektoniczna: Vessel DWT data (zatwierdzona)
- Faza 1: Estymacja DWT z AIS Type 5 dimensions (darmowe z aisstream.io)
- Faza 2: Datalastic API (199 EUR/mies. Starter) dla precyzyjnych danych statków bez Type 5
- Formuła estymacji: `length × beam × draught × Cb` (block coefficient per vessel type)

---

## MILESTONE 5 — Kpler Intelligence
> Cel: voyage tracking, volume estimation, predictive analytics, AI chat, compliance — poziom Kpler
> Czas: 6-8 tygodni (4 fazy: A→B→C→D)
> Dependency: Milestone 2 complete (AIS + commodity data flowing)
> WAŻNE: Faza A musi być ukończona przed B. Fazy C i D mogą być równoległe.

---

### Issue #39
**Title:** `[M5-A] AIS Type 5 ingestion — vessel static data`
**Labels:** `milestone-5` `backend` `data-ingestion` `voyage-intelligence` `priority-critical`

**Cel:** Subskrybować AIS Type 5 (ShipStaticData) z aisstream.io i zapisywać dane statyczne statków.

**Acceptance criteria:**
- [ ] `FilterMessageTypes` w ais_stream.py rozszerzony o `"ShipStaticData"`
- [ ] Nowa tabela `vessel_static_data` z kolumnami: mmsi (PK), imo, vessel_name, callsign, ship_type, vessel_type (enum), dim_a/b/c/d, length_m (generated), beam_m (generated), dwt_estimate, max_draught, flag_country, updated_at
- [ ] Parser `_parse_static_data()` w ais_stream.py obsługuje Type 5 messages
- [ ] UPSERT: jeśli mmsi istnieje → aktualizuj (dane statyczne mogą się zmieniać)
- [ ] DWT estymacja: `length × beam × draught × Cb` gdzie Cb = {tanker: 0.85, bulk: 0.83, container: 0.65, default: 0.70}
- [ ] Alembic migration: CREATE TABLE vessel_static_data + ALTER TABLE ports ADD COLUMN radius_km, unlocode
- [ ] Test: test_type5_parser, test_dwt_estimation
- [ ] Po 1h działania: `SELECT COUNT(*) FROM vessel_static_data` > 1000

**Pliki do modyfikacji:**
- `backend/ingestion/ais_stream.py` — +ShipStaticData subscription, +parser, +upsert batch
- `backend/migrations/versions/xxx_add_vessel_static_data.py` — nowa migracja

**Blokuje:** #40, #41, #42, #43, #44, #45

---

### Issue #40
**Title:** `[M5-A] Port geofencing — radius-based enter/exit detection`
**Labels:** `milestone-5` `backend` `database` `voyage-intelligence` `priority-critical`

**Cel:** Dodać PostGIS, radius geofence do portów i funkcję wykrywającą wejście/wyjście statku z portu.

**Acceptance criteria:**
- [ ] `CREATE EXTENSION IF NOT EXISTS postgis` w migracji
- [ ] ALTER TABLE ports ADD COLUMN radius_km REAL DEFAULT 5.0, ADD COLUMN unlocode TEXT
- [ ] SQL function `is_in_port(lat, lon) → port_id | NULL` — sprawdza czy punkt jest w promieniu dowolnego portu
- [ ] Indeks PostGIS na ports: `CREATE INDEX ON ports USING gist (ST_MakePoint(longitude, latitude)::geography)`
- [ ] Endpoint `GET /api/v1/ports/{id}/vessels` — lista statków aktualnie w geofence portu
- [ ] Test: test_is_in_port_singapore, test_is_in_port_outside

**Pliki do modyfikacji:**
- `backend/migrations/versions/xxx_add_postgis_port_geofence.py`
- `backend/api/v1/ports.py` — nowy endpoint

**Dependency:** #39 (potrzebujemy vessel positions + static data)

---

### Issue #41
**Title:** `[M5-A] Voyage detection — automatic trip tracking`
**Labels:** `milestone-5` `backend` `voyage-intelligence` `priority-critical`

**Cel:** Celery task wykrywający wejście/wyjście statku z portu i tworzący/zamykający voyage.

**Acceptance criteria:**
- [ ] Nowy ENUM `voyage_status_type`: `'underway', 'arrived', 'floating_storage', 'completed'`
- [ ] Nowa tabela `voyages` (id UUID PK, mmsi BIGINT NOT NULL, imo TEXT, vessel_type vessel_type, origin_port_id UUID REFERENCES ports(id), dest_port_id UUID REFERENCES ports(id), departure_time TIMESTAMPTZ, arrival_time TIMESTAMPTZ, status voyage_status_type NOT NULL DEFAULT 'underway', laden_status TEXT, cargo_type commodity_type, volume_estimate REAL, distance_nm REAL, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)
- [ ] Trigger `set_updated_at` na tabeli `voyages`
- [ ] Indeksy: `(mmsi)`, `(status)`, `(origin_port_id)`, `(dest_port_id)`, `(departure_time DESC)`, `(cargo_type)`
- [ ] Celery task `detect_voyages` co 5 minut:
  - Dla każdego statku z pozycją w last 10 min: sprawdź `is_in_port(lat, lon)`
  - Jeśli statek BYŁ w porcie (had active voyage z status=arrived lub brak voyage) i TERAZ jest poza portem → nowy voyage (status=underway, origin_port_id=ten port)
  - Jeśli statek miał voyage z status=underway i TERAZ jest w porcie → zamknij voyage (arrival_time=now, dest_port_id=ten port, status=arrived)
- [ ] Stan "ostatni znany port" przechowywany w Redis: `vessel:{mmsi}:last_port`
- [ ] `GET /api/v1/voyages?mmsi=123456789` — lista voyages dla statku
- [ ] `GET /api/v1/voyages?status=underway&commodity=crude_oil` — aktywne voyages per commodity
- [ ] Test: test_voyage_created_on_departure, test_voyage_closed_on_arrival

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_create_voyages.py`
- `backend/ingestion/voyage_detector.py` — logika detekcji
- `backend/api/v1/voyages.py` — endpointy
- Rozszerz `backend/simulation/tasks.py` — Celery Beat co 5 min

**Dependency:** #39, #40

---

### Issue #42
**Title:** `[M5-A] Laden/ballast classification + volume estimation`
**Labels:** `milestone-5` `backend` `voyage-intelligence` `priority-high`

**Cel:** Określić czy statek płynie załadowany (laden) czy pusty (ballast) i estymować objętość ładunku.

**Acceptance criteria:**
- [ ] Laden/ballast: porównanie `current_draught` (z vessel_positions) vs `max_draught` (z vessel_static_data)
  - Jeśli current_draught > 0.6 × max_draught → laden
  - W przeciwnym razie → ballast
- [ ] Volume estimation: `dwt_estimate × (current_draught / max_draught) × load_factor`
  - load_factor: {tanker: 0.95, bulk_carrier: 0.90, container: 0.80, default: 0.85}
- [ ] Voyage.laden_status i voyage.volume_estimate aktualizowane przy departure
- [ ] `GET /api/v1/voyages/{id}` zwraca laden_status i volume_estimate
- [ ] Cargo type inference: jeśli origin_port ma commodities[] → przypisz najczęstszy commodity
- [ ] Test: test_laden_classification, test_volume_estimation_tanker

**Pliki do modyfikacji:**
- `backend/ingestion/voyage_detector.py` — rozszerz o laden/volume
- `backend/api/v1/voyages.py` — rozszerz response

**Dependency:** #39, #41

---

### Issue #43
**Title:** `[M5-A] Floating storage detection`
**Labels:** `milestone-5` `backend` `voyage-intelligence` `priority-medium`

**Cel:** Wykrywanie statków pełniących rolę floating storage (laden, stoi >7 dni).

**Acceptance criteria:**
- [ ] Celery task `detect_floating_storage` co 1h:
  - Znajdź statki z laden_status=laden, speed < 0.5 knot, poza portem, od >7 dni w tym samym miejscu (±0.01°)
  - Ustaw voyage.status = 'floating_storage'
  - Wygeneruj alert typu 'ais_anomaly' z tytułem "Floating storage detected: {vessel_name}"
- [ ] `GET /api/v1/voyages?status=floating_storage` — lista floating storage
- [ ] Dashboard widget: total floating storage volume per commodity
- [ ] Test: test_floating_storage_detected

**Pliki do modyfikacji:**
- `backend/ingestion/voyage_detector.py` — dodaj floating storage logic
- Rozszerz `backend/simulation/tasks.py` — Celery Beat co 1h

**Dependency:** #41, #42

---

### Issue #44
**Title:** `[M5-A] Trade flow enrichment — link voyages to trade_flows`
**Labels:** `milestone-5` `backend` `voyage-intelligence` `priority-high`

**Cel:** Połączyć voyage data z trade_flows — dodać real-time volume do statycznych UN Comtrade tras.

**Acceptance criteria:**
- [ ] Gdy voyage zamknięty (arrived): match origin_port → destination_port do istniejącej trade_flows route
- [ ] Jeśli match: aktualizuj `trade_flows.volume_mt` += voyage.volume_estimate (rolling 30 dni)
- [ ] Jeśli brak match: utwórz nowy trade_flow z danymi voyage
- [ ] `GET /api/v1/commodities/flows?commodity=crude_oil&source=live` — filtr na live vs comtrade dane
- [ ] Test: test_trade_flow_enriched_by_voyage

**Pliki do modyfikacji:**
- `backend/ingestion/voyage_detector.py` — trade flow linkage po arrival
- `backend/api/v1/commodities.py` — rozszerz /flows o source filter

**Dependency:** #41, #42

---

### Issue #45
**Title:** `[M5-A] Frontend — voyage tracking panel + vessel detail enrichment`
**Labels:** `milestone-5` `frontend` `voyage-intelligence` `priority-high`

**Cel:** UI pokazujące aktywne voyages, vessel detail z DWT/laden, floating storage na mapie.

**Acceptance criteria:**
- [ ] Vessel popup rozszerzony: DWT, laden/ballast badge, current voyage (origin → destination), ETA
- [ ] Nowy tab w right panel: "Voyages" — lista aktywnych voyages z volume, origin→dest, ETA
- [ ] Floating storage markers na mapie (inny kolor/ikona)
- [ ] Voyage trail: linia od origin do aktualnej pozycji (dashed) + predicted path do destination (dotted)
- [ ] Filtr: laden/ballast, commodity, origin region

**Pliki do modyfikacji:**
- `frontend/src/components/map/VesselPopup.vue` — rozszerz
- `frontend/src/stores/useMapStore.ts` — dodaj voyages
- `frontend/src/views/MapView.vue` — floating storage layer

**Dependency:** #41, #42, #43

---

### Issue #46
**Title:** `[M5-B] Destination prediction — historical pattern model`
**Labels:** `milestone-5` `backend` `predictive-analytics` `priority-high`

**Cel:** Predykcja portu docelowego na podstawie historycznych voyages i AIS destination field.

**Acceptance criteria:**
- [ ] Model: dla statku opuszczającego port X z cargo Y → najczęstszy destination z historii
- [ ] Fallback: jeśli brak historii → użyj AIS destination field z Type 5
- [ ] Confidence score: count(matching_voyages) / count(total_voyages_from_origin)
- [ ] `GET /api/v1/voyages/{id}/prediction` → { predicted_port, confidence, alternatives[] }
- [ ] Aktualizuj prediction co godzinę (statek zbliżający się do portu → wyższa confidence)
- [ ] Test: test_destination_prediction_with_history, test_prediction_fallback_ais

**Pliki do stworzenia:**
- `backend/analytics/destination_predictor.py`
- Rozszerz `backend/api/v1/voyages.py`

**Dependency:** #41 (wymaga ≥2 tygodni danych voyage)

---

### Issue #47
**Title:** `[M5-B] ETA calculation + port congestion index`
**Labels:** `milestone-5` `backend` `predictive-analytics` `priority-high`

**Cel:** Kalkulacja ETA na podstawie dystansu i średniej prędkości + indeks kongestii portu.

**Acceptance criteria:**
- [ ] ETA: `remaining_distance / avg_speed_last_6h` (simple great-circle distance)
- [ ] Port congestion: ile statków z speed < 1 knot w geofence portu (waiting to berth)
- [ ] Congestion index 0-100: `min(waiting_vessels × 5, 100)`
- [ ] `GET /api/v1/ports/{id}/congestion` → { congestion_index, waiting_vessels, avg_wait_hours, risk_level }
- [ ] Celery task `update_port_congestion` co 15 min
- [ ] Test: test_eta_calculation, test_port_congestion_index

**Pliki do stworzenia:**
- `backend/analytics/eta_calculator.py`
- `backend/analytics/port_congestion.py`
- Rozszerz `backend/api/v1/ports.py`

**Dependency:** #40, #41

---

### Issue #48
**Title:** `[M5-B] Supply flow prediction — trend analysis`
**Labels:** `milestone-5` `backend` `predictive-analytics` `priority-medium`

**Cel:** Trend wolumenu per commodity per route — predykcja 7/30/90 dni.

**Acceptance criteria:**
- [ ] Rolling average volume per route: 7d, 30d, 90d
- [ ] Trend direction: growing/declining/stable (porównanie 7d vs 30d average)
- [ ] `GET /api/v1/commodities/flows/{commodity}/trend?route=SGSIN-NLRTM` → { trend, volume_7d, volume_30d, volume_90d, prediction_30d }
- [ ] Simple linear regression for 30d prediction
- [ ] Test: test_supply_trend_growing

**Pliki do stworzenia:**
- `backend/analytics/supply_trend.py`
- Rozszerz `backend/api/v1/commodities.py`

**Dependency:** #44 (wymaga enriched trade flows)

---

### Issue #49
**Title:** `[M5-B] Frontend — predictive analytics dashboard`
**Labels:** `milestone-5` `frontend` `predictive-analytics` `priority-high`

**Cel:** Dashboard z destination predictions, port congestion, supply trends.

**Acceptance criteria:**
- [ ] Port congestion cards: top 10 portów z najwyższą kongestią, kliknięcie → detail panel
- [ ] Voyage prediction: na mapie pokazuj predicted destination (dotted line + confidence %)
- [ ] Supply trend charts: per commodity → volume trend 90d z prediction line
- [ ] Alerts: jeśli port congestion > 80 → visual alert na mapie
- [ ] ETA display: w voyage list i vessel popup

**Pliki do modyfikacji:**
- `frontend/src/views/MapView.vue` — prediction lines, congestion overlay
- `frontend/src/views/CommodityDashboard.vue` — trend charts
- Nowy: `frontend/src/components/PortCongestionPanel.vue`

**Dependency:** #46, #47, #48

---

### Issue #50
**Title:** `[M5-C] AI Chat — Gemini-powered supply chain assistant`
**Labels:** `milestone-5` `backend` `frontend` `ai-chat` `priority-high`

**Cel:** Chat AI odpowiadający na pytania o dane w systemie (statki, voyages, ceny, alerty).

**Acceptance criteria:**
- [ ] `POST /api/v1/chat` — wysyła pytanie, zwraca odpowiedź
- [ ] Backend: Gemini 2.5 Flash API z kontekstem danych (structured data injection)
- [ ] Kontekst: ostatnie ceny, aktywne voyages, top alerty, port congestion — budowany dynamicznie per pytanie
- [ ] Fallback: Claude Haiku 4.5 jeśli Gemini timeout/error
- [ ] SSE streaming response: `GET /api/v1/chat/{id}/stream`
- [ ] Rate limit: Free=10/dzień, Pro=100/dzień, Business=unlimited
- [ ] Frontend: chat panel (slide-out z prawej), historia konwersacji (session-based)
- [ ] Test: test_chat_returns_response, test_chat_rate_limit

**Pliki do stworzenia:**
- `backend/api/v1/chat.py`
- `backend/ai/chat_engine.py` — context builder + Gemini/Claude API
- `frontend/src/components/ChatPanel.vue`
- `frontend/src/stores/useChatStore.ts`

**Dependency:** Milestone 2 complete (dane muszą płynąć)

---

### Issue #51
**Title:** `[M5-C] CSV/Excel export + webhook notifications`
**Labels:** `milestone-5` `backend` `export` `priority-medium`

**Cel:** Export danych do CSV/Excel i user-configurable webhooks.

**Acceptance criteria:**
- [ ] `GET /api/v1/export/vessels?format=csv&bbox=...` — streaming CSV z pozycjami
- [ ] `GET /api/v1/export/voyages?format=xlsx&commodity=crude_oil` — Excel z voyages
- [ ] `GET /api/v1/export/prices?format=csv&commodity=coal&from=2026-01-01` — ceny historyczne
- [ ] Pro+ only (RBAC check)
- [ ] Webhooks: `POST /api/v1/webhooks` — zarejestruj URL + event types
- [ ] Webhook delivery: POST JSON payload na zarejestrowany URL przy nowym alert/voyage
- [ ] HMAC signature verification (user secret)
- [ ] Test: test_csv_export, test_webhook_delivery

**Pliki do stworzenia:**
- `backend/api/v1/export.py`
- `backend/api/v1/webhooks.py`
- `backend/webhooks/delivery.py`

**Dependency:** Brak (standalone)

---

### Issue #52
**Title:** `[M5-D] OFAC/EU sanctions import + vessel screening`
**Labels:** `milestone-5` `backend` `compliance` `priority-high`

**Cel:** Import list sankcyjnych i automatyczne sprawdzanie statków.

**Acceptance criteria:**
- [ ] Nowa tabela `sanctioned_entities` (id, source, entity_type, name, imo, mmsi, aliases[], country, program, updated_at)
- [ ] Celery task `import_sanctions` co 24h:
  - OFAC SDN: download CSV z US Treasury, parse vessel entries
  - EU Consolidated: download XML, parse vessel entries
- [ ] Screening: przy każdym nowym vessel_static_data record → sprawdź vs sanctioned_entities (mmsi, imo, name fuzzy match)
- [ ] Jeśli match → alert typu 'compliance' z severity=critical
- [ ] `GET /api/v1/compliance/sanctions?mmsi=123` — sprawdź status sankcji
- [ ] `GET /api/v1/compliance/flagged` — lista oflagowanych statków
- [ ] Test: test_ofac_import, test_vessel_screening_match

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_create_sanctioned_entities.py`
- `backend/ingestion/sanctions.py` — OFAC + EU import
- `backend/compliance/screening.py` — vessel matching
- `backend/api/v1/compliance.py`

**Dependency:** #39

---

### Issue #53
**Title:** `[M5-D] AIS gap detection + STS transfer detection`
**Labels:** `milestone-5` `backend` `compliance` `priority-medium`

**Cel:** Wykrywanie AIS gaps (statek znika) i Ship-to-Ship transfers (podejrzane spotkania).

**Acceptance criteria:**
- [ ] AIS gap: Celery task co 30 min — jeśli statek miał pozycje, zniknął na >6h, pojawił się >50km dalej → alert 'ais_gap'
- [ ] STS detection: dwóch statków <500m od siebie, oba speed < 2 knots, oba laden → alert 'sts_transfer'
- [ ] `GET /api/v1/compliance/ais-gaps?hours=24` — lista gap events
- [ ] `GET /api/v1/compliance/sts-events?hours=48` — lista STS events
- [ ] Test: test_ais_gap_detected, test_sts_detected

**Pliki do stworzenia:**
- `backend/compliance/ais_gap_detector.py`
- `backend/compliance/sts_detector.py`
- Rozszerz `backend/api/v1/compliance.py`
- Rozszerz `backend/simulation/tasks.py` — Celery Beat

**Dependency:** #39

---

### Issue #54
**Title:** `[M5-D] Frontend — compliance dashboard`
**Labels:** `milestone-5` `frontend` `compliance` `priority-medium`

**Cel:** Dashboard compliance z flagged vessels, AIS gaps, STS events.

**Acceptance criteria:**
- [ ] Tab "Sanctions": lista oflagowanych statków z severity, source, match type
- [ ] Tab "AIS Gaps": mapa z zaznaczonymi gap locations (last seen → reappeared)
- [ ] Tab "STS Events": lista spotkań z mapą lokalizacji
- [ ] Filtr: date range, severity, vessel type
- [ ] Export do CSV (re-use #51)

**Pliki do stworzenia:**
- `frontend/src/views/ComplianceDashboard.vue`
- `frontend/src/stores/useComplianceStore.ts`
- Route w `frontend/src/main.ts`

**Dependency:** #52, #53

---

## Zaktualizowany dependency graph

```
M0: #1 → #2 → #3 → #4 → #5 → #6 → #36
                                          ↓
M1: #7 → #8 → #9 → #10
    #11 → #12
    #13 → #14 → #15
    #16 (launch)
                                          ↓
M2: #17 → #18 → #19 → #20 → #21
    #22 → #23
    #24 → #25
    #37 (onboarding)
                                          ↓
          ┌──── M3: #26 → #27 → #28 → #29 → #30 → #31
          │
M2 done ──┤
          │
          └──── M5-A: #39 → #40 → #41 → #42 → #43 → #44 → #45
                                                ↓
                       M5-B: #46 → #47 → #48 → #49
                                                ↓
                       M5-C: #50, #51 (równoległe)
                       M5-D: #52 → #53 → #54
                                          ↓
M4: #32 → #33 → #34 → #35 → #38 (Sentry)
```

**WAŻNE:** M3 (Simulation) i M5-A (Voyage Intelligence) mogą być robione RÓWNOLEGLE po ukończeniu M2 — nie blokują się nawzajem.

---

### Issue #55
**Title:** `[M5-C] Weather overlay — Open-Meteo + Copernicus marine data on map`
**Labels:** `milestone-5` `frontend` `backend` `priority-medium`

**Cel:** Warstwa pogodowa na mapie — wiatr, fale, sztormy wpływające na szlaki żeglugowe.

**Acceptance criteria:**
- [ ] Backend proxy: `GET /api/v1/weather?bbox=...` → pobiera dane z Open-Meteo Marine API (darmowe, bez klucza)
- [ ] Parametry: wind_speed_10m, wind_direction_10m, wave_height, wave_period
- [ ] Frontend: toggle "Weather" na mapie — wind arrows + wave height color overlay (MapLibre heatmap layer)
- [ ] Storm alerts: jeśli wind > 40 knots w regionie z aktywnymi voyages → alert 'weather_warning'
- [ ] Cache w Redis: 15 min TTL (API rate limit friendly)
- [ ] Opcjonalnie: Copernicus CMEMS ocean currents overlay (darmowe, wymaga rejestracji)
- [ ] Test: test_weather_proxy, test_storm_alert

**Pliki do stworzenia:**
- `backend/api/v1/weather.py`
- `backend/ingestion/weather.py` — Open-Meteo + CMEMS fetcher
- `frontend/src/components/map/WeatherLayer.vue`

**Dependency:** Brak (standalone, ale najlepiej po #13 map)

---

### Issue #56
**Title:** `[M5-C] Energy infrastructure map — pipelines, refineries, LNG terminals`
**Labels:** `milestone-5` `frontend` `backend` `priority-medium`

**Cel:** Warstwa infrastruktury energetycznej na mapie — jak Bloomberg BMAP.

**Acceptance criteria:**
- [ ] Import danych z Global Energy Monitor (GEM) wiki — oil/gas pipelines, LNG terminals, coal mines, refineries
- [ ] Tabela `infrastructure_assets` (id UUID PK, type TEXT NOT NULL, name TEXT NOT NULL, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, status TEXT, capacity REAL, commodity commodity_type, country TEXT, source_url TEXT, metadata JSONB, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeksy: PostGIS spatial index na `(latitude, longitude)`, `(type)`, `(commodity)`
- [ ] Typy: pipeline, refinery, lng_terminal, coal_mine, oil_field, storage_facility
- [ ] Celery task `import_gem_data` — monthly refresh z GEM API/CSV
- [ ] Opcjonalnie: OpenStreetMap Overpass query dla pipeline routes (GeoJSON LineStrings)
- [ ] Frontend: toggle "Infrastructure" na mapie — ikony per type, kliknięcie → popup z details
- [ ] `GET /api/v1/infrastructure?type=lng_terminal&bbox=...`
- [ ] Test: test_infrastructure_import, test_infrastructure_bbox

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_create_infrastructure_assets.py`
- `backend/scripts/seed_infrastructure.py` — GEM import
- `backend/api/v1/infrastructure.py`
- `frontend/src/components/map/InfrastructureLayer.vue`

**Dependency:** Brak (standalone)

---

### Issue #57
**Title:** `[M5-A] Vessel ownership + Equasis lookup`
**Labels:** `milestone-5` `backend` `voyage-intelligence` `priority-medium`

**Cel:** Wzbogacenie danych statku o ownership chain — właściciel, operator, klasyfikacja.

**Acceptance criteria:**
- [ ] ALTER TABLE vessel_static_data ADD COLUMNS: owner TEXT, operator TEXT, classification_society TEXT, year_built INT, gross_tonnage REAL
- [ ] Endpoint `GET /api/v1/vessels/{mmsi}/ownership` → { owner, operator, classification, year_built, gross_tonnage }
- [ ] Equasis integration (darmowe konto, scraping za zgodą ToS):
  - Lookup by IMO → owner, operator, classification society, flag history
  - Cache w bazie (vessel_static_data) — refresh co 30 dni
- [ ] Fallback: jeśli Equasis niedostępne → dane z AIS Type 5 only
- [ ] Vessel detail panel na frontendzie rozszerzony o ownership info
- [ ] Test: test_ownership_lookup, test_ownership_cache

**Pliki do stworzenia:**
- `backend/ingestion/equasis.py` — lookup + cache
- Rozszerz `backend/api/v1/vessels.py`
- Rozszerz `backend/migrations/versions/xxx_extend_vessel_static_data.py`

**Dependency:** #39

---

### Issue #58
**Title:** `[M5-B] Carbon emission estimation per voyage`
**Labels:** `milestone-5` `backend` `predictive-analytics` `priority-medium`

**Cel:** Estymacja emisji CO2 per voyage — jak Argus Carbon Cost of Freight.

**Acceptance criteria:**
- [ ] Formuła IMO: `CO2 = fuel_consumption × 3.114` (tonnes CO2 per tonne fuel)
- [ ] Fuel consumption estymacja: `distance_nm × daily_consumption / (24 × speed)` where daily_consumption from vessel type/size lookup table
- [ ] Lookup table: { tanker_vlcc: 80t/d, tanker_suezmax: 55t/d, bulk_capesize: 45t/d, bulk_panamax: 32t/d, container_large: 150t/d, lng_carrier: 130t/d, default: 35t/d }
- [ ] CII rating estimate: Annual Efficiency Ratio = CO2 / (DWT × distance) → A/B/C/D/E rating
- [ ] Voyage response rozszerzony: `co2_estimate_tonnes`, `fuel_estimate_tonnes`, `cii_rating`
- [ ] `GET /api/v1/analytics/emissions?commodity=crude_oil&period=30d` → total emissions per commodity route
- [ ] Test: test_co2_estimation_vlcc, test_cii_rating

**Pliki do stworzenia:**
- `backend/analytics/emissions.py`
- Rozszerz `backend/api/v1/voyages.py`
- Rozszerz `backend/api/v1/analytics.py` (nowy)

**Dependency:** #41, #42

---

### Issue #59
**Title:** `[M5-D] AIS spoofing detection`
**Labels:** `milestone-5` `backend` `compliance` `priority-medium`

**Cel:** Wykrywanie manipulacji AIS (GNSS spoofing) — jak Windward.

**Acceptance criteria:**
- [ ] Celery task `detect_ais_spoofing` co 15 min:
  - **Teleportation**: pozycja skacze >100km w <1h → alert 'ais_spoofing'
  - **Impossible speed**: speed_knots > 35 dla cargo/tanker (max fizyczny ~25) → flag
  - **Circular patterns**: statek "krąży" w małym obszarze z identycznymi pozycjami (±0.001°) przez >2h → flag
  - **Position on land**: lat/lon odpowiada lądowi (prosty check: major land polygons) → flag
- [ ] ⚠️ NIE tworzyć osobnej tabeli `ais_anomaly_events` — użyć istniejącej `alert_events` z `type='ais_spoofing'` i `metadata JSONB` (anomaly_type, details, resolved)
- [ ] Wymaga rozszerzenia `alert_type` enum (patrz Issue #91)
- [ ] `GET /api/v1/compliance/spoofing?hours=24` — lista spoofing events (query z alert_events WHERE type='ais_spoofing')
- [ ] Alert z severity=warning, link do vessel detail
- [ ] Test: test_teleportation_detected, test_impossible_speed_detected

**Pliki do stworzenia:**
- `backend/compliance/spoofing_detector.py`
- Rozszerz `backend/api/v1/compliance.py`
- Rozszerz `backend/simulation/tasks.py` — Celery Beat co 15 min

**Dependency:** #39

---

### Issue #60
**Title:** `[M5-B] Smart price alerts — statistical anomaly detection`
**Labels:** `milestone-5` `backend` `predictive-analytics` `priority-high`

**Cel:** Automatyczne alerty cenowe — jak uproszczona wersja Argus Possibility Curves.

**Acceptance criteria:**
- [ ] Celery task `detect_price_anomalies` co 1h:
  - Dla każdego commodity: oblicz rolling mean i std (30d)
  - Jeśli latest_price > mean + 2σ → alert 'price_spike' severity=warning
  - Jeśli latest_price > mean + 3σ → alert 'price_spike' severity=critical
  - Jeśli latest_price < mean - 2σ → alert 'price_drop' severity=warning
- [ ] Kontekst w alercie: `"{commodity} price at ${price} — {σ_count}σ above 30-day average (${mean}±${std})"`
- [ ] Price momentum: jeśli 3 kolejne daily prices rosnące > 1σ → alert 'price_trend' z body "Sustained upward pressure"
- [ ] `GET /api/v1/analytics/price-bands?commodity=crude_oil` → { mean, std, upper_2σ, lower_2σ, current, percentile }
- [ ] Frontend: Bollinger-style bands na price chart (±1σ, ±2σ shaded areas)
- [ ] Test: test_price_spike_detected, test_price_bands_calculation

**Pliki do stworzenia:**
- `backend/analytics/price_anomaly.py`
- `backend/api/v1/analytics.py` — nowy router
- Rozszerz `frontend/src/views/CommodityDashboard.vue` — Bollinger bands

**Dependency:** #17 (commodity_prices flowing)

---

## Zaktualizowany dependency graph (final)

```
M0: #1 → #2 → #3 → #4 → #5 → #6 → #36
                                          ↓
M1: #7 → #8 → #9 → #10
    #11 → #12
    #13 → #14 → #15
    #16 (launch)
                                          ↓
M2: #17 → #18 → #19 → #20 → #21
    #22 → #23
    #24 → #25
    #37 (onboarding)
                                          ↓
          ┌──── M3: #26 → #27 → #28 → #29 → #30 → #31
          │
M2 done ──┤
          │
          └──── M5-A: #39 → #40 → #41 → #42 → #43 → #44 → #45
                  │                         ↓
                  │    M5-B: #46 → #47 → #48 → #49
                  │            #58 (emissions)  #60 (price alerts)
                  │                         ↓
                  │    M5-C: #50 (AI chat), #51 (export)
                  │          #55 (weather), #56 (infrastructure)
                  │                         ↓
                  └──  M5-D: #52 → #53 → #54
                             #57 (ownership)  #59 (spoofing)
                                          ↓
M4: #32 → #33 → #34 → #35 → #38 (Sentry)
```

**Total: 109 issues across 7 milestones (M0-M6)** — pełny graph na końcu pliku

---

### Issue #61
**Title:** `[M5-B] Expand commodity coverage — yfinance daily futures (20+ commodities)`
**Labels:** `milestone-5` `backend` `data-ingestion` `priority-high`

**Cel:** Rozszerzenie pokrycia cenowego z 10 do 30+ commodities używając yfinance (futures z COMEX/NYMEX/CBOT/ICE).

**Acceptance criteria:**
- [ ] Nowy ingestion module `backend/ingestion/yfinance_prices.py`
- [ ] Pobiera daily settlement prices z yfinance dla 20+ tickers:
  - Precious metals: `GC=F` (gold), `SI=F` (silver), `PL=F` (platinum), `PA=F` (palladium)
  - Energy: `RB=F` (gasoline RBOB), `HO=F` (heating oil)
  - Agriculture: `ZC=F` (corn), `ZR=F` (rice), `CT=F` (cotton), `SB=F` (sugar), `KC=F` (coffee), `CC=F` (cocoa), `ZL=F` (soybean oil), `ZM=F` (soybean meal), `LE=F` (cattle), `LBS=F` (lumber)
- [ ] Celery Beat: co 4h w godzinach handlowych (14:00-22:00 UTC, poniedziałek-piątek)
- [ ] Batch download: `yf.download(tickers, period="1d")` — jeden request na wszystkie tickery
- [ ] Mapowanie ticker → commodity_type enum + benchmark name + unit
- [ ] Rozszerzenie `commodity_type_enum` o nowe typy: `gold, silver, platinum, gasoline, diesel, corn, rice, cotton, sugar, coffee, cocoa, uranium, lumber, cattle` (UWAGA: `palladium` już istnieje w enum — NIE dodawać ponownie)
- [ ] Użyj `ALTER TYPE commodity_type ADD VALUE 'xxx'` — nie można w transakcji, każda wartość osobno
- [ ] Fallback: jeśli yfinance timeout → skip, retry w następnym cyklu
- [ ] `pip install yfinance` dodany do requirements.txt
- [ ] Test: test_yfinance_batch_download, test_ticker_mapping

**Pliki do stworzenia:**
- `backend/ingestion/yfinance_prices.py`
- Alembic migration: rozszerzenie `commodity_type_enum`

**Dependency:** #17 (commodity_prices infrastructure)

---

### Issue #62
**Title:** `[M5-B] Expand commodity coverage — FRED daily spot + monthly global`
**Labels:** `milestone-5` `backend` `data-ingestion` `priority-high`

**Cel:** Dodatkowe dane cenowe z FRED API — daily US energy spot + monthly global (IMF-sourced).

**Acceptance criteria:**
- [ ] Nowy ingestion module `backend/ingestion/fred_prices.py`
- [ ] FRED API key w config: `FRED_API_KEY`
- [ ] Daily US energy spot prices (9 series):
  - `DCOILWTICO` (WTI), `DCOILBRENTEU` (Brent), `DHHNGSP` (Henry Hub)
  - `DGASNYH` (gasoline NY), `DHOILNYH` (heating oil), `DDFUELUSGULF` (diesel)
  - `DPROPANEMBTX` (propane), `WJFUELUSGULF` (jet fuel, weekly)
- [ ] Monthly global prices (15 series — metals, agriculture):
  - `PZINCUSDM`, `PLEADUSDM`, `PTINUSDM` (base metals)
  - `PPOILUSDM` (palm oil), `PRUBBUSDM` (rubber), `PBARLUSDM` (barley)
  - `PNGASEUUSDM` (natural gas EU TTF), `PNGASJPUSDM` (LNG Asia)
  - `PCOALAUUSDM` (coal Australia)
  - `PURANUSDM` (uranium)
  - `PCOFFOTMUSDM` (coffee), `PCOTTINDUSDM` (cotton), `PSUGAISAUSDM` (sugar), `PCOCOUSDM` (cocoa)
- [ ] Celery Beat: daily series co 6h, monthly series co 24h
- [ ] Deduplikacja: `ON CONFLICT (time, commodity, benchmark) DO NOTHING`
- [ ] Rate limit: max 120 requests/min — batch wisely
- [ ] Test: test_fred_daily_fetch, test_fred_monthly_fetch

**Pliki do stworzenia:**
- `backend/ingestion/fred_prices.py`
- Config: `FRED_API_KEY: str = ""`

**Dependency:** #17

---

### Issue #63
**Title:** `[M5-B] Expand commodity coverage — World Bank Pink Sheet (fertilizers + niche)`
**Labels:** `milestone-5` `backend` `data-ingestion` `priority-medium`

**Cel:** Import World Bank Commodity Price Data (Pink Sheet) — jedyne darmowe źródło cen nawozów.

**Acceptance criteria:**
- [ ] Celery task `import_world_bank_prices` — co tydzień (dane aktualizowane raz/miesiąc)
- [ ] Download Excel z: `https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx`
- [ ] Parse z openpyxl: sheet "Monthly Prices" — kolumny per commodity, wiersze per miesiąc
- [ ] Fertilizer commodities (unikalne — brak w innych źródłach):
  - Urea (Eastern Europe bulk), DAP, TSP, Potassium Chloride (potash), Phosphate Rock
- [ ] Dodatkowe niche commodities jeśli brak z FRED/yfinance:
  - Steel (hot-rolled coil), Natural Rubber, Fish Meal
- [ ] Rozszerzenie `commodity_type_enum`: `urea, dap, potash, phosphate`
- [ ] `pip install openpyxl` dodany do requirements.txt
- [ ] Test: test_world_bank_excel_parse, test_fertilizer_prices_imported

**Pliki do stworzenia:**
- `backend/ingestion/world_bank_prices.py`
- Alembic migration: rozszerzenie `commodity_type_enum` o fertilizers

**Dependency:** #17

---

## Decyzja architektoniczna: Commodity price sources (zatwierdzona)

### Priorytet źródeł (ten sam commodity, wiele źródeł):
1. **yfinance daily futures** — najświeższe, ale nieoficjalne API
2. **FRED daily spot** — oficjalne, US-focused
3. **EIA API v2** — oficjalne, energy-only
4. **Nasdaq Data Link** — istniejąca integracja
5. **FRED monthly (IMF)** — globalne, ale monthly
6. **World Bank Pink Sheet** — niche (fertilizers), monthly

### Pokrycie docelowe: 42 commodities w 7 kategoriach
- Energy: 10 (crude WTI/Brent, gasoline, diesel, jet fuel, heating oil, propane, LNG Henry Hub, nat gas TTF, LNG Asia)
- Precious metals: 4 (gold, silver, platinum, palladium)
- Base metals: 7 (copper, aluminium, nickel, zinc, lead, tin, iron ore)
- Agriculture: 12 (wheat, corn, soybeans, soybean oil/meal, rice, cotton, sugar, coffee, cocoa, palm oil, rubber, barley)
- Fertilizers: 4 (urea, DAP, potash, phosphate)
- Other: 3 (uranium, lumber, cattle)
- Coal: 2 (Newcastle/Australia, API2 proxy)

### vs Argus: 42/100+ = 42% coverage, ale pokrywa 95% commodities śledzonych w żegludze morskiej

---

## Decyzja architektoniczna: Konsolidacja Celery tasków (audyt)

### Problem
yfinance jest używany w 3 issues (#61, #69, #85) i FRED w 2 issues (#62, #86). Osobne Celery taski ryzykują:
- yfinance: IP block przy >2K req/h (3 równoczesne taski)
- FRED: przekroczenie 120 req/min limitu

### Rozwiązanie
1. **Jeden centralny yfinance task** `fetch_all_yfinance`: uruchamiany co 4h, pobiera:
   - Commodity prices (#61): 20+ futures tickers
   - Forward curves (#69): multi-month contracts per commodity
   - Carbon ETF proxy (#85): KRBN, ECF=F
   - Bunker proxy (#87): HO=F
   - Rate limiter: max 5 req/sec, shared session, backoff on 429
2. **Jeden centralny FRED task** `fetch_all_fred`: uruchamiany co 6h, pobiera:
   - Daily spot prices (#62): 9 energy series
   - Monthly global (#62): 15 series
   - Macro indicators (#86): DXY, interest rates, EPU, industrial production
   - Batch wisely: max 60 series per run, stagger with 0.5s delay
3. **Staggered schedules** — nie uruchamiać yfinance i FRED w tej samej minucie

### Implementacja
- `backend/ingestion/yfinance_unified.py` — single entry point
- `backend/ingestion/fred_unified.py` — single entry point
- Każdy issue (#61, #62, #69, #85, #86, #87) definiuje SWOJĄ konfigurację (tickery/serie), ale task runner jest wspólny

---

## Decyzja architektoniczna: Rozszerzenie `alert_type` enum (audyt)

### Problem
Aktualny `alert_type` enum ma 5 wartości: `ais_anomaly, price_move, news_event, port_congestion, geopolitical`. Issues M5/M6 potrzebują 15+ nowych typów.

### Rozwiązanie
**Zmienić `alert_type` z ENUM na TEXT z CHECK constraint:**
```sql
ALTER TABLE alert_events ALTER COLUMN type TYPE TEXT;
ALTER TABLE alert_events ADD CONSTRAINT alert_type_check CHECK (
  type IN ('ais_anomaly', 'price_move', 'news_event', 'port_congestion', 'geopolitical',
           'ais_spoofing', 'ais_gap', 'sts_transfer', 'sanctions_match',
           'price_spike', 'price_drop', 'price_trend',
           'cot_extreme', 'inventory_surprise', 'refinery_margin_squeeze',
           'correlation_break', 'seasonal_anomaly', 'curve_flip',
           'fx_move', 'conflict_risk', 'geopolitical_risk_elevated',
           'rig_count_shift', 'natgas_storage_low', 'crop_stress',
           'bunker_price_spike', 'search_spike', 'warehouse_drawdown',
           'recession_signal')
);
```
Łatwiejsze rozszerzanie niż ENUM (ALTER TABLE vs ALTER TYPE ADD VALUE).

### Issue: #91 (nowy — patrz niżej)

---

### Issue #64
**Title:** `[M5-B] CFTC Commitment of Traders (COT) dashboard`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-high`

**Cel:** Tygodniowe dane pozycjonowania traderów z CFTC — najważniejszy darmowy dataset w commodity trading.

**Acceptance criteria:**
- [ ] Celery task `import_cftc_cot` — co piątek 22:00 UTC (dane publikowane 15:30 ET)
- [ ] Download z: `https://www.cftc.gov/dea/newcot/deacom.txt` (Commodity, Combined)
- [ ] Parse CSV: Commercial Net, Non-Commercial Net, Managed Money Net, Swap Dealer Net per commodity
- [ ] Nowa tabela `cot_reports` (id UUID PK, commodity commodity_type NOT NULL, report_date TIMESTAMPTZ NOT NULL, commercial_long BIGINT, commercial_short BIGINT, commercial_net BIGINT, noncommercial_long BIGINT, noncommercial_short BIGINT, noncommercial_net BIGINT, managed_money_net BIGINT, open_interest BIGINT, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(commodity, report_date DESC)`
- [ ] Mapowanie CFTC market codes → nasze commodity_type: `CL=crude_oil`, `NG=lng`, `GC=gold`, `SI=silver`, `HG=copper`, `W=wheat`, `C=corn`, `S=soybeans`, etc.
- [ ] `GET /api/v1/analytics/cot?commodity=crude_oil` → { data: [{ date, commercial_net, managed_money_net, open_interest }], trend: "net_long_increasing" }
- [ ] Frontend: COT chart — bar chart (net positions) overlaid with price line, 52-week comparison
- [ ] Extremes alert: jeśli managed_money_net > 90th percentile (2-year rolling) → alert 'cot_extreme'
- [ ] Test: test_cftc_parse, test_cot_extremes_alert

**Pliki do stworzenia:**
- `backend/ingestion/cftc_cot.py`
- `backend/migrations/versions/xxx_create_cot_reports.py`
- `backend/api/v1/analytics.py` — rozszerz o /cot endpoint
- `frontend/src/components/analytics/COTChart.vue`

**Dependency:** Brak (standalone, darmowe dane)

---

### Issue #65
**Title:** `[M5-B] EIA petroleum inventory dashboard`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-high`

**Cel:** Tygodniowe dane zapasów ropy i produktów z EIA — najbardziej market-moving weekly data release.

**Acceptance criteria:**
- [ ] Celery task `import_eia_inventories` — co środa 17:00 UTC (dane 10:30 ET)
- [ ] EIA API v2 series:
  - Crude stocks: `PET.WCESTUS1.W` (commercial), `PET.WCSSTUS1.W` (SPR)
  - Gasoline stocks: `PET.WGTSTUS1.W`
  - Distillate stocks: `PET.WDISTUS1.W`
  - Refinery utilization: `PET.WPULEUS3.W`
  - Net imports: `PET.WCRNTUS2.W`
  - Cushing stocks: `PET.W_EPC0_SAX_YCUOK_MBBL.W`
- [ ] Tabela `eia_inventories` (id UUID PK, series TEXT NOT NULL, value REAL, unit TEXT, time TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(series, time DESC)` + UNIQUE `(series, time)`
- [ ] `GET /api/v1/analytics/inventories?series=crude_stocks` → { current, previous, change, forecast, vs_5yr_avg, vs_5yr_range }
- [ ] Frontend: inventory chart z 5-year range band (min-max shaded) + current year line + prev year line
- [ ] Inventory surprise alert: jeśli |actual_change - consensus| > 3M bbl → alert 'inventory_surprise'
- [ ] Test: test_eia_inventory_fetch, test_inventory_surprise

**Pliki do stworzenia:**
- `backend/ingestion/eia_inventories.py`
- `backend/migrations/versions/xxx_create_eia_inventories.py`
- `frontend/src/components/analytics/InventoryChart.vue`

**Dependency:** Brak (standalone, darmowe dane z EIA API)

---

### Issue #66
**Title:** `[M5-B] Crack spread / refinery margin calculator`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-medium`

**Cel:** Automatyczne obliczanie crack spreadów — wskaźnik rentowności rafinerii.

**Acceptance criteria:**
- [ ] Formuły:
  - 3-2-1 crack: `(2 × gasoline + 1 × heating_oil - 3 × WTI) / 3`
  - 2-1-1 crack: `(1 × gasoline + 1 × heating_oil - 2 × WTI) / 2`
  - Brent crack: `(2 × gasoline + 1 × gasoil - 3 × Brent) / 3`
- [ ] Kalkulacja z istniejących commodity_prices (gasoline, heating_oil, WTI, Brent)
- [ ] Celery task `calculate_crack_spreads` co 4h — wstaw do commodity_prices z benchmark='3-2-1 Crack'
- [ ] `GET /api/v1/analytics/cracks` → { usgc_321, usgc_211, nwe_brent_crack, history[] }
- [ ] Frontend: crack spread chart z seasonal overlay (5-year average)
- [ ] Alert: jeśli crack < 5yr minimum → 'refinery_margin_squeeze' warning
- [ ] Test: test_crack_321_calculation

**Pliki do stworzenia:**
- `backend/analytics/crack_spreads.py`
- Rozszerz `backend/api/v1/analytics.py`
- `frontend/src/components/analytics/CrackSpreadChart.vue`

**Dependency:** #61, #62 (wymaga cen gasoline, heating oil, crude)

---

### Issue #67
**Title:** `[M5-B] Commodity correlation matrix`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-medium`

**Cel:** Interaktywna heatmapa korelacji między wszystkimi commodities — kluczowe narzędzie risk management.

**Acceptance criteria:**
- [ ] `GET /api/v1/analytics/correlations?window=30d` → matryca korelacji Pearson dla 42 commodities
- [ ] Rolling windows: 7d, 30d, 90d
- [ ] Obliczanie z commodity_prices (daily returns)
- [ ] Cache w Redis: 1h TTL (heavy computation)
- [ ] Frontend: interactive heatmap (D3.js lub lightweight lib) — kliknięcie na cell → scatter plot dwóch commodities
- [ ] Correlation break alert: jeśli |correlation_change| > 0.3 w ciągu 7 dni → alert 'correlation_break'
- [ ] Top pairs: ranking najbardziej i najmniej skorelowanych par
- [ ] Test: test_correlation_matrix_symmetric, test_correlation_break_alert

**Pliki do stworzenia:**
- `backend/analytics/correlations.py`
- Rozszerz `backend/api/v1/analytics.py`
- `frontend/src/components/analytics/CorrelationMatrix.vue`

**Dependency:** #17 (wymaga commodity_prices z min 30 dni historii)

---

### Issue #68
**Title:** `[M5-B] Seasonal pattern analysis`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-medium`

**Cel:** Overlay ceny current year vs historical seasonal patterns — jak SpreadCharts.

**Acceptance criteria:**
- [ ] `GET /api/v1/analytics/seasonal?commodity=crude_oil&years=5` → { current_year[], avg_5yr[], percentile_bands: { p10[], p25[], p75[], p90[] } }
- [ ] Normalizacja: day-of-year (1-366) → price indexed to Jan 1 = 100
- [ ] Percentile bands: min, p10, p25, median, p75, p90, max z ostatnich N lat
- [ ] Frontend: area chart z shaded percentile bands + bold current year line
- [ ] Deviation indicator: "Current price is at 85th percentile vs 5-year seasonal pattern"
- [ ] Seasonal anomaly alert: jeśli price > p95 lub < p5 seasonal → alert
- [ ] Test: test_seasonal_normalization, test_percentile_bands

**Pliki do stworzenia:**
- `backend/analytics/seasonal.py`
- Rozszerz `backend/api/v1/analytics.py`
- `frontend/src/components/analytics/SeasonalChart.vue`

**Dependency:** #17 (wymaga min 2 lata historii cenowej)

---

### Issue #69
**Title:** `[M5-B] Forward curve / term structure viewer`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-high`

**Cel:** Wizualizacja krzywych futures — contango vs backwardation, sygnał dla storage economics.

**Acceptance criteria:**
- [ ] yfinance: pobierz multiple contract months per commodity (np. CL: CLF27, CLG27, CLH27... — 12 months out)
- [ ] Celery task `fetch_forward_curves` co 4h
- [ ] Tabela `forward_curves` (id, commodity, contract_month, expiry_date, settlement_price, time, created_at)
- [ ] `GET /api/v1/analytics/forward-curve?commodity=crude_oil` → { contracts: [{ month, expiry, price }], structure: "contango|backwardation|flat", m1_m2_spread }
- [ ] Frontend: line chart — x=expiry month, y=price. Toggle: today vs 1 week ago vs 1 month ago
- [ ] Contango/backwardation alert: jeśli structure zmieni się → alert 'curve_flip'
- [ ] Calendar spread tracking: M1-M6, M1-M12 spread over time
- [ ] Test: test_forward_curve_fetch, test_contango_detection

**Pliki do stworzenia:**
- `backend/ingestion/forward_curves.py`
- `backend/migrations/versions/xxx_create_forward_curves.py`
- `frontend/src/components/analytics/ForwardCurveChart.vue`

**Dependency:** #61 (yfinance infrastructure)

---

### Issue #70
**Title:** `[M5-B] Supply/demand balance sheets — EIA STEO + USDA WASDE`
**Labels:** `milestone-5` `backend` `frontend` `predictive-analytics` `priority-medium`

**Cel:** Miesięczne bilanse podaży/popytu per commodity — fundament analizy fundamentalnej.

**Acceptance criteria:**
- [ ] **Oil S/D**: EIA STEO (Short-Term Energy Outlook) — monthly API fetch
  - World production, consumption, OECD stocks, implied balance (surplus/deficit)
  - `GET /api/v1/analytics/balance/crude_oil` → { production_mbd, consumption_mbd, stock_change, balance, forecast_3m }
- [ ] **Agriculture S/D**: USDA WASDE — monthly PDF/API parse
  - Corn, wheat, soybeans: production, consumption, ending stocks, stocks-to-use ratio
  - `GET /api/v1/analytics/balance/wheat` → { production_mt, consumption_mt, ending_stocks, stocks_to_use_pct }
- [ ] Tabela `supply_demand_balance` (id, commodity, period, production, consumption, stock_change, ending_stocks, source, created_at)
- [ ] Frontend: stacked bar chart (production vs consumption) + line (ending stocks)
- [ ] Test: test_steo_fetch, test_wasde_parse

**Pliki do stworzenia:**
- `backend/ingestion/eia_steo.py`
- `backend/ingestion/usda_wasde.py`
- `backend/migrations/versions/xxx_create_supply_demand.py`
- `frontend/src/components/analytics/BalanceChart.vue`

**Dependency:** Brak (standalone, darmowe dane)

---

### Issue #71
**Title:** `[M5-A] Fleet / company-level analytics`
**Labels:** `milestone-5` `backend` `frontend` `voyage-intelligence` `priority-medium`

**Cel:** Agregacja na poziomie floty/firmy — kto czym handluje, fleet utilization, vessel age.

**Acceptance criteria:**
- [ ] Grupowanie vessel_static_data po `owner` i `operator`
- [ ] `GET /api/v1/fleet?owner=Maersk` → { vessel_count, total_dwt, avg_age, utilization_pct, vessels: [...] }
- [ ] `GET /api/v1/fleet/top?by=dwt&vessel_type=tanker&limit=20` → top 20 tanker owners
- [ ] Fleet utilization: laden_voyages / total_voyages per company (30d rolling)
- [ ] Vessel age profile: histogram year_built per owner
- [ ] `GET /api/v1/fleet/{owner}/exposure` → { commodities: { crude_oil: 45%, coal: 30%, ... }, regions: { asia: 60%, ... } }
- [ ] Frontend: fleet table z sortowaniem, kliknięcie → fleet detail z charts
- [ ] Test: test_fleet_aggregation, test_utilization_rate

**Pliki do stworzenia:**
- `backend/api/v1/fleet.py`
- `frontend/src/views/FleetAnalytics.vue`
- `frontend/src/stores/useFleetStore.ts`

**Dependency:** #39, #41, #57 (wymaga vessel_static_data + voyages + ownership)

---

### Issue #72
**Title:** `[M5-A] Port analytics dashboard — dwell time, turnaround, throughput`
**Labels:** `milestone-5` `backend` `frontend` `voyage-intelligence` `priority-medium`

**Cel:** Głębsza analityka portowa — czas oczekiwania, obrót, trendy przepustowości.

**Acceptance criteria:**
- [ ] Metryki per port (obliczane z voyages + vessel_positions):
  - **Dwell time**: median czas od arrival do departure (godziny)
  - **Turnaround time**: czas od wejścia do geofence do wyjścia
  - **Queue length**: statki z speed < 1 knot w geofence (waiting)
  - **Throughput**: suma volume_estimate per tydzień/miesiąc
  - **Vessel count**: unique vessels per day
- [ ] Celery task `calculate_port_analytics` co 1h
- [ ] Tabela `port_analytics` (port_id, period, dwell_time_median, turnaround_median, queue_length, throughput_mt, vessel_count, time)
- [ ] `GET /api/v1/ports/{id}/analytics?period=30d` → { dwell_time, turnaround, queue, throughput_trend, vs_avg }
- [ ] `GET /api/v1/ports/ranking?by=congestion&limit=20` → top 20 most congested ports
- [ ] Frontend: port detail panel z sparklines per metryka + 90d trend
- [ ] Test: test_dwell_time_calculation, test_port_ranking

**Pliki do stworzenia:**
- `backend/analytics/port_analytics.py`
- `backend/migrations/versions/xxx_create_port_analytics.py`
- Rozszerz `backend/api/v1/ports.py`
- `frontend/src/components/analytics/PortAnalyticsPanel.vue`

**Dependency:** #40, #41 (wymaga port geofencing + voyages)

---

### Issue #73
**Title:** `[M5-C] Notification integrations — Slack, Telegram, Discord`
**Labels:** `milestone-5` `backend` `priority-medium`

**Cel:** Push alertów do team channels — traderzy żyją w Slack/Telegram, nie w emailu.

**Acceptance criteria:**
- [ ] Notification channels per user: `POST /api/v1/notifications/channels` → { type: "slack|telegram|discord", webhook_url, enabled }
- [ ] **Slack**: Incoming Webhook URL → POST JSON z alert data (rich formatting z blocks)
- [ ] **Telegram**: Bot API — user podaje chat_id, bot wysyła wiadomości
- [ ] **Discord**: Webhook URL → POST embed z alert data
- [ ] Dispatcher: przy nowym alert matching user subscription → send to all enabled channels
- [ ] Rate limit: max 10 notifications/h per channel (anti-spam)
- [ ] `GET /api/v1/notifications/channels` — lista kanałów usera
- [ ] `DELETE /api/v1/notifications/channels/{id}` — usuń kanał
- [ ] Frontend: settings page → tab "Notifications" z formularzem dodawania kanałów
- [ ] Test: test_slack_webhook_send, test_telegram_send, test_rate_limit

**Pliki do stworzenia:**
- `backend/notifications/dispatcher.py`
- `backend/notifications/slack.py`
- `backend/notifications/telegram.py`
- `backend/notifications/discord.py`
- `backend/api/v1/notifications.py`
- `backend/migrations/versions/xxx_create_notification_channels.py`

**Dependency:** #21 (alert subscriptions)

---

### Issue #74
**Title:** `[M5-C] Historical event replay — "time machine"`
**Labels:** `milestone-5` `backend` `frontend` `priority-medium`

**Cel:** Replay historycznych disruptions — "co się stało gdy Suez był zablokowany?" z synchronizacją price/flow/news.

**Acceptance criteria:**
- [ ] Tabela `historical_events` (id, name, start_date, end_date, commodities[], description, impact_summary, tags[])
- [ ] Pre-seed 10 major events:
  - Ever Given Suez blockage (2021-03-23 to 2021-03-29)
  - Russia-Ukraine invasion (2022-02-24)
  - Houthi Red Sea attacks (2023-11 to present)
  - COVID demand crash (2020-03 to 2020-05)
  - OPEC+ production cuts (2023-06)
  - Nord Stream sabotage (2022-09-26)
  - Australia floods (2022-02)
  - China coal import ban (2020-10)
  - Texas freeze (2021-02-13 to 2021-02-17)
  - Panama Canal drought (2023-07 to 2024-01)
- [ ] `GET /api/v1/events` → lista historycznych eventów
- [ ] `GET /api/v1/events/{id}/replay` → { prices_before, prices_after, price_impact_pct, affected_commodities, timeline[] }
- [ ] Frontend: timeline slider — przesuń w czasie, zobacz:
  - Price chart z highlighted event period
  - % zmiana cen affected commodities
  - News/alerty z tego okresu
- [ ] "Compare to current": overlay current situation vs historical event
- [ ] Test: test_event_replay_suez, test_price_impact_calculation

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_create_historical_events.py`
- `backend/scripts/seed_historical_events.py`
- `backend/api/v1/events.py`
- `frontend/src/views/EventReplay.vue`
- `frontend/src/stores/useEventStore.ts`

**Dependency:** #17 (wymaga commodity_prices z historią)

---

### Issue #75
**Title:** `[M5-C] Python SDK + interactive API documentation portal`
**Labels:** `milestone-5` `backend` `priority-medium`

**Cel:** Python SDK dla quantów + interaktywna dokumentacja API — jak Vortexa SDK.

**Acceptance criteria:**
- [ ] Python package `supplyshock` generowany z OpenAPI spec (FastAPI auto-generates)
- [ ] Użycie: `pip install supplyshock`
  ```python
  from supplyshock import Client
  client = Client(api_key="sk_live_xxx")
  prices = client.commodities.prices(commodity="crude_oil", days=30)
  voyages = client.voyages.list(status="underway", commodity="crude_oil")
  ```
- [ ] Auto-generated z `openapi-python-client` lub `fern`
- [ ] Typed responses (Pydantic models)
- [ ] Async support: `async with AsyncClient(...) as client:`
- [ ] Interactive API docs: Swagger UI + ReDoc na `/docs` i `/redoc`
- [ ] API playground na frontend: formularz do testowania endpointów z live response
- [ ] README z quickstart examples
- [ ] Publish na PyPI (CI/CD)
- [ ] Test: test_sdk_price_fetch, test_sdk_auth

**Pliki do stworzenia:**
- `sdk/python/supplyshock/` — auto-generated package
- `sdk/python/setup.py`
- `sdk/python/README.md`
- `.github/workflows/publish-sdk.yml`

**Dependency:** Milestone 2+ (API musi być stabilne)

---

## MILESTONE 6 — Maximum Data Coverage (M6)
> Cel: Maksymalne pokrycie danych — makro, FX, geopolityka, porty, rolnictwo, energia, carbon, sentiment
> Czas: Po M5 (lub równolegle z M5-C/D)
> Blokuje: nic (standalone data feeds)

---

### Issue #76
**Title:** `[M6] IMF PortWatch — daily chokepoint & port disruption data`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-critical`

**Cel:** Import danych z IMF PortWatch — najlepsza darmowa baza portów i chokepoints na świecie (2,033 portów, daily updates).

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/imf_portwatch.py`
- [ ] IMF PortWatch API: `https://portwatch.imf.org/api/` — free, no key needed
- [ ] Dane:
  - Daily port-level trade volume estimates (import/export, TEU + tonnes)
  - Chokepoint transit counts (Suez, Panama, Hormuz, Malacca, Bosphorus, etc.)
  - Port disruption indicators (delays, closures, congestion scores)
  - Country-level trade flow aggregates
- [ ] Celery Beat: co 6h — download latest data
- [ ] Mapowanie IMF port IDs → nasze `ports.id` (via UNLOCODE match)
- [ ] Wzbogacenie tabeli `ports`: ADD COLUMNS `imf_portwatch_id TEXT`, `daily_import_teu REAL`, `daily_export_teu REAL`
- [ ] ⚠️ **UWAGA (audyt):** Zweryfikować granularity danych IMF PortWatch — część może być monthly/quarterly, nie daily. Dostosować Celery schedule.
- [ ] Nowa tabela `chokepoint_transits` (id UUID PK, node_id UUID NOT NULL REFERENCES bottleneck_nodes(id), transit_date TIMESTAMPTZ NOT NULL, vessel_count INT, total_teu REAL, total_tonnes REAL, avg_delay_hours REAL, source TEXT DEFAULT 'imf_portwatch', created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(node_id, transit_date DESC)` — FK do `bottleneck_nodes` zamiast free-text name (spójność z istniejącą tabelą `chokepoint_status`)
- [ ] `GET /api/v1/chokepoints/imf?name=suez&days=30` → { daily_transits[], avg_volume, trend }
- [ ] Frontend: chokepoint dashboard z IMF data — wykres transitów + porównanie YoY
- [ ] Test: test_imf_portwatch_fetch, test_chokepoint_mapping

**Pliki do stworzenia:**
- `backend/ingestion/imf_portwatch.py`
- `backend/migrations/versions/xxx_create_chokepoint_transits.py`
- Rozszerz `backend/api/v1/chokepoints.py`

**Dependency:** #25 (chokepoint infrastructure)

---

### Issue #77
**Title:** `[M6] DBnomics — single API to 80+ statistical providers`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** DBnomics jako unified gateway do IMF, OECD, Eurostat, ECB, UN — jeden API zamiast wielu.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/dbnomics.py`
- [ ] DBnomics API: `https://db.nomics.world/api/v22/` — free, no key, no rate limits
- [ ] Serie do pobrania:
  - **IMF IFS**: industrial production indices (30+ krajów) → leading indicator popytu
  - **OECD MEI**: PMI composites (US, EU, China, Japan) → manufacturing activity
  - **Eurostat**: EU energy imports by source country (monthly)
  - **ECB**: EUR/USD, EUR exchange rates (daily)
  - **UN Comtrade**: bilateral trade volumes per commodity/country (monthly)
  - **IMF DOTS**: Direction of Trade Statistics (import/export by country pair)
- [ ] Nowa tabela `macro_indicators` (id, provider, series_id, country, indicator_name, value, unit, period, frequency, created_at)
- [ ] Celery Beat: co 12h (dane aktualizowane daily/monthly)
- [ ] `GET /api/v1/macro?indicator=pmi&country=US,CN,EU` → { series: [{ country, data: [{ period, value }] }] }
- [ ] `GET /api/v1/macro/trade-flows?commodity=crude_oil&exporter=SA&importer=CN` → bilateral trade volumes
- [ ] Frontend: Macro dashboard — PMI overlay na commodity price chart, trade flow Sankey
- [ ] Test: test_dbnomics_fetch, test_macro_pmi_overlay

**Pliki do stworzenia:**
- `backend/ingestion/dbnomics.py`
- `backend/migrations/versions/xxx_create_macro_indicators.py`
- `backend/api/v1/macro.py`
- `frontend/src/views/MacroDashboard.vue`
- `frontend/src/components/analytics/PMIOverlay.vue`

**Dependency:** Brak (standalone)

---

### Issue #78
**Title:** `[M6] Frankfurter API — unlimited free FX rates`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** Kursy walut — kluczowe dla przeliczania cen commodities i analizy wpływu dolara na surowce.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/frankfurter_fx.py`
- [ ] Frankfurter API: `https://api.frankfurter.dev/` — free, no key, unlimited requests
- [ ] Pary walutowe (15+):
  - USD/EUR, USD/GBP, USD/JPY, USD/CNY, USD/INR, USD/BRL, USD/RUB, USD/TRY
  - USD/AUD (commodity currency), USD/CAD (oil), USD/NOK (oil), USD/ZAR (metals)
  - USD/SGD (shipping), USD/KRW (trade)
- [ ] Celery Beat: co 4h (dane aktualizowane daily)
- [ ] Tabela `fx_rates` (id UUID PK, base_currency TEXT NOT NULL, quote_currency TEXT NOT NULL, rate DOUBLE PRECISION NOT NULL, time TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(base_currency, quote_currency, time DESC)` + UNIQUE constraint
- [ ] DXY (Dollar Index) proxy: obliczany z koszyka walut (EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, SEK 4.2%, CHF 3.6%)
- [ ] `GET /api/v1/fx?pairs=USD/EUR,USD/CNY&days=30` → { pairs: [{ pair, rates: [{ date, rate }] }] }
- [ ] `GET /api/v1/fx/dxy?days=90` → { dxy: [{ date, value }], correlation_to_oil }
- [ ] Frontend: FX panel + DXY vs commodity price overlay
- [ ] Alert: jeśli |daily_change| > 1.5% → alert 'fx_move'
- [ ] Test: test_frankfurter_fetch, test_dxy_calculation

**Pliki do stworzenia:**
- `backend/ingestion/frankfurter_fx.py`
- `backend/migrations/versions/xxx_create_fx_rates.py`
- `backend/api/v1/fx.py`
- `frontend/src/components/analytics/FXPanel.vue`

**Dependency:** Brak (standalone)

---

### Issue #79
**Title:** `[M6] ACLED conflict data — geopolitical supply disruption risk`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** Geocoded armed conflict events — dla modelowania ryzyka disruptions w regionach produkcji/tranzytu surowców.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/acled.py`
- [ ] ⚠️ **RYZYKO PRAWNE:** ACLED "free for non-commercial/academic" — SupplyShock jest komercyjny SaaS. Przed wdrożeniem: zweryfikować koszt licencji komercyjnej lub użyć GDELT (#18) jako darmowej alternatywy (mniej precyzyjne geocoding, ale zero ryzyka)
- [ ] ACLED API: `https://acleddata.com/acled-api/` — wymaga klucza + licencji komercyjnej
- [ ] **Fallback (jeśli ACLED za drogi):** GDELT GKG z filtrem conflict events + geocoding — gorszy ale darmowy
- [ ] Dane: conflict events (battles, explosions, riots, protests) z latitude/longitude, date, actor, fatalities, notes
- [ ] Filtrowanie: tylko eventy w proximity (<100km) do:
  - Oil/gas fields, pipelines, refineries (z #56 infrastructure_assets)
  - Major shipping lanes / chokepoints (z #25 bottleneck_nodes)
  - Major ports (z #40 ports)
- [ ] Nowa tabela `conflict_events` (id UUID PK, source_id TEXT, event_date TIMESTAMPTZ NOT NULL, event_type TEXT, sub_event_type TEXT, country TEXT, admin1 TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, fatalities INT, notes TEXT, nearest_asset_id UUID, nearest_asset_type TEXT, distance_km REAL, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeksy: `(event_date DESC)`, PostGIS spatial index na `(latitude, longitude)`, `(nearest_asset_id)`
- [ ] Celery Beat: co 24h — download last 7 days of events
- [ ] Risk score per region: count of events in 30d rolling window, weighted by severity (fatalities, proximity to infrastructure)
- [ ] `GET /api/v1/risk/conflicts?region=middle_east&days=30` → { events[], risk_score, trend }
- [ ] Frontend: conflict events na mapie (red dots), heatmap intensity overlay
- [ ] Alert: cluster of 5+ events near infrastructure in 7d → alert 'conflict_risk'
- [ ] Test: test_acled_fetch, test_proximity_filter, test_risk_score

**Pliki do stworzenia:**
- `backend/ingestion/acled.py`
- `backend/migrations/versions/xxx_create_conflict_events.py`
- `backend/api/v1/risk.py`
- `frontend/src/components/map/ConflictLayer.vue`

**Dependency:** #56 (infrastructure assets for proximity matching)

---

### Issue #80
**Title:** `[M6] GPR Index — quantitative geopolitical risk`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** Geopolitical Risk Index (Caldara & Iacoviello) — miesięczny indeks bazujący na news articles, używany przez banki centralne.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/gpr_index.py`
- [ ] Źródło: `https://www.matteoiacoviello.com/gpr.htm` — free Excel/CSV download, monthly updates
- [ ] Serie:
  - GPR Index (global) — main geopolitical risk
  - GPR Threats Index — war/terrorism threats
  - GPR Acts Index — actual geopolitical events
  - Country-specific GPR: US, UK, China, Russia, Saudi Arabia, Iran, etc.
- [ ] Celery Beat: co tydzień (dane monthly)
- [ ] Wstaw do `macro_indicators` tabeli (z #77): provider='GPR', indicator_name='gpr_index'
- [ ] `GET /api/v1/macro/gpr?countries=global,US,CN&months=24` → { series: [{ country, gpr: [{ month, value }] }] }
- [ ] Frontend: GPR chart z overlay na commodity price — "czy geopolityka napędza wzrost ceny?"
- [ ] Alert: jeśli GPR > 2σ above 5-year mean → alert 'geopolitical_risk_elevated'
- [ ] Test: test_gpr_fetch, test_gpr_alert

**Pliki do stworzenia:**
- `backend/ingestion/gpr_index.py`
- Rozszerz `backend/api/v1/macro.py`

**Dependency:** #77 (macro_indicators table)

---

### Issue #81
**Title:** `[M6] Baker Hughes rig count — weekly drilling activity`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** Tygodniowe dane rig count — leading indicator produkcji ropy. Gdy rig count rośnie, produkcja wzrośnie za 3-6 miesięcy.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/baker_hughes.py`
- [ ] Źródło: Baker Hughes publishes weekly CSV na stronie — scrape lub static URL
  - Backup: EIA API v2 ma rig count: `RIGS.RES02-0000.W`
- [ ] Dane: US total rigs, oil rigs, gas rigs, basin-level (Permian, Eagle Ford, Bakken, etc.)
- [ ] Nowa tabela `rig_counts` (id UUID PK, time TIMESTAMPTZ NOT NULL, region TEXT NOT NULL, rig_type TEXT NOT NULL, count INT, week_change INT, year_change INT, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(region, rig_type, time DESC)`
- [ ] Celery Beat: co piątek 19:00 UTC (publikacja 13:00 ET)
- [ ] `GET /api/v1/analytics/rigs?region=US&type=oil&weeks=52` → { current, history[], yoy_change, trend }
- [ ] Frontend: rig count chart z overlay na WTI price (shifted 6 months — leading indicator)
- [ ] Alert: jeśli weekly_change > ±10% → alert 'rig_count_shift'
- [ ] Test: test_rig_count_fetch, test_rig_count_alert

**Pliki do stworzenia:**
- `backend/ingestion/baker_hughes.py`
- `backend/migrations/versions/xxx_create_rig_counts.py`
- `backend/api/v1/analytics.py` — rozszerz o /rigs endpoint
- `frontend/src/components/analytics/RigCountChart.vue`

**Dependency:** Brak (standalone)

---

### Issue #82
**Title:** `[M6] JODI Oil Database — global oil supply/demand (IEA alternative)`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** JODI (Joint Organisations Data Initiative) — darmowa alternatywa dla IEA oil data. Dane z 90+ krajów.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/jodi.py`
- [ ] ⚠️ **RYZYKO DOSTĘPNOŚCI:** JODI NIE ma programmatic API — strona wymaga ręcznego downloadu Excel/CSV. Sprawdzić:
  - **Opcja A:** UN Data API (`https://data.un.org/`) — ma częściowe JODI series (zweryfikować pokrycie)
  - **Opcja B:** Ręczny monthly import — download CSV z `https://www.jodidata.org/`, upload do systemu
  - **Opcja C:** DBnomics (#77) może mieć JODI series via authorized provider — zweryfikować
- [ ] Źródło primarne: UN Data API (jeśli pokrywa wymagane series), backup: ręczny import CSV
- [ ] Dane monthly per country:
  - Production (crude oil, NGL, condensate)
  - Refinery intake/output
  - Imports/exports
  - Closing stocks
  - Demand (products delivered)
- [ ] Wzbogacenie tabeli `supply_demand_balance` (z #70): dodaj source='JODI', country-level breakdown
- [ ] Celery Beat: co tydzień (dane monthly z 2-month lag)
- [ ] `GET /api/v1/analytics/balance/crude_oil?source=jodi&countries=SA,RU,US,CN` → country-level S/D
- [ ] Frontend: country comparison chart — kto produkuje ile, kto importuje ile
- [ ] Test: test_jodi_parse, test_country_level_balance

**Pliki do stworzenia:**
- `backend/ingestion/jodi.py`
- Rozszerz `backend/api/v1/analytics.py`

**Dependency:** #70 (supply_demand_balance table)

---

### Issue #83
**Title:** `[M6] EIA natural gas storage + SPR levels + refinery outages`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** Dodatkowe serie EIA — natural gas storage (weekly, market-moving), SPR levels, refinery outages.

**Acceptance criteria:**
- [ ] Rozszerzenie `backend/ingestion/eia_inventories.py` o nowe serie:
  - **Natural gas storage**: `NG.NW2_EPG0_SWO_R48_BCF.W` (weekly working gas in storage)
  - **Natural gas storage by region**: East, Midwest, Mountain, Pacific, South Central
  - **SPR levels**: `PET.WCSSTUS1.W` (Strategic Petroleum Reserve)
  - **Refinery outages**: `PET.WPULEUS3.W` (utilization) + `PET.WGIRIUS2.W` (inputs)
- [ ] Natural gas storage: 5-year range band (like crude inventories, #65)
- [ ] SPR tracker: current level, withdrawal rate, days of cover
- [ ] `GET /api/v1/analytics/inventories/natgas` → { current_bcf, vs_5yr_avg, injection_withdrawal, forecast }
- [ ] `GET /api/v1/analytics/spr` → { current_mbl, withdrawal_rate, days_of_cover, historical[] }
- [ ] Frontend: natural gas storage chart z seasonal band, SPR tracker widget
- [ ] Alert: natgas storage < 5yr minimum → alert 'natgas_storage_low'
- [ ] Test: test_natgas_storage_fetch, test_spr_tracker

**Pliki do stworzenia:**
- Rozszerz `backend/ingestion/eia_inventories.py`
- Rozszerz `backend/api/v1/analytics.py`
- `frontend/src/components/analytics/NatGasStorageChart.vue`
- `frontend/src/components/analytics/SPRTracker.vue`

**Dependency:** #65 (EIA inventory infrastructure)

---

### Issue #84
**Title:** `[M6] USDA NASS + FAS — crop data & export sales`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** USDA agricultural data — crop progress, weekly export sales, global S/D. Fundamentalne dla agri commodities.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/usda.py`
- [ ] **USDA NASS QuickStats API**: `https://quickstats.nass.usda.gov/api/` — free, key required
  - Crop progress: planting %, emerged %, good/excellent condition %
  - Corn, soybeans, wheat, cotton — weekly updates during season (Apr-Nov)
- [ ] **USDA FAS OpenData**: `https://apps.fas.usda.gov/OpenData/api/` — free, key required
  - Weekly export sales (corn, wheat, soybeans) — kluczowe dla rynku
  - PSD (Production, Supply, Distribution) — global S/D per country
- [ ] Nowa tabela `crop_data` (id UUID PK, commodity commodity_type NOT NULL, indicator TEXT NOT NULL, value REAL, unit TEXT, time TIMESTAMPTZ NOT NULL, source TEXT, created_at TIMESTAMPTZ DEFAULT now())
- [ ] Indeks: `(commodity, indicator, time DESC)`
- [ ] Celery Beat: NASS co poniedziałek 16:00 UTC, FAS co czwartek 12:00 UTC
- [ ] `GET /api/v1/analytics/crops/progress?commodity=corn` → { planting_pct, condition: { good_excellent: 65 }, vs_5yr_avg }
- [ ] `GET /api/v1/analytics/crops/exports?commodity=wheat&weeks=12` → { weekly_sales[], cumulative, vs_pace }
- [ ] Frontend: crop progress chart (area chart: condition breakdown) + export sales bar chart
- [ ] Alert: condition good/excellent < 50% → alert 'crop_stress'
- [ ] Test: test_nass_fetch, test_fas_export_sales

**Pliki do stworzenia:**
- `backend/ingestion/usda.py`
- `backend/migrations/versions/xxx_create_crop_data.py`
- `backend/api/v1/crops.py`
- `frontend/src/components/analytics/CropProgressChart.vue`

**Dependency:** Brak (standalone)

---

### Issue #85
**Title:** `[M6] Carbon prices — EU ETS + global carbon credit tracking`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** Ceny uprawnień do emisji CO2 — rosnące znaczenie dla kosztów shippingu i energii.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/carbon_prices.py`
- [ ] Źródła:
  - **EU ETS**: yfinance ticker `KRBN` (KraneShares Global Carbon ETF) jako proxy, lub `ECF=F` (ICE EUA futures)
  - **Ember Climate**: `https://ember-energy.org/data/carbon-price-tracker/` — free CSV z European + global carbon prices
  - **ICAP Allowance Price Explorer**: `https://icapcarbonaction.com/en/ets-prices` — 30+ ETS worldwide
- [ ] Commodities do dodania: EU_ETS, UK_ETS, RGGI (US Northeast), California_CCA, Korea_KAU, China_pilot
- [ ] Rozszerzenie `commodity_type_enum`: `carbon_eu_ets, carbon_uk_ets, carbon_us_rggi, carbon_california`
- [ ] Celery Beat: co 6h (EU ETS via yfinance), co 24h (inne z Ember/ICAP)
- [ ] `GET /api/v1/commodities/carbon` → { eu_ets: { price, change, trend }, uk_ets: {...}, ... }
- [ ] Frontend: carbon price dashboard z comparison chart (EU vs UK vs US)
- [ ] Integracja z #58 (emissions): koszt emisji per voyage = CO2_tonnes × carbon_price
- [ ] Test: test_carbon_price_fetch, test_emission_cost_calculation

**Pliki do stworzenia:**
- `backend/ingestion/carbon_prices.py`
- Rozszerz `backend/api/v1/commodities.py`
- `frontend/src/components/analytics/CarbonPriceChart.vue`

**Dependency:** #58 (carbon emissions per voyage)

---

### Issue #86
**Title:** `[M6] FRED expanded — DXY, interest rates, EPU, industrial production`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-high`

**Cel:** Dodatkowe serie makro z FRED — każda z tych serii wpływa na ceny surowców.

**Acceptance criteria:**
- [ ] Rozszerzenie `backend/ingestion/fred_prices.py` o nowe serie:
  - **Dollar Index proxy**: `DTWEXBGS` (Trade Weighted US Dollar Index: Broad, Goods and Services) — daily
  - **Interest rates**: `DFF` (Fed Funds Rate), `DGS10` (10Y Treasury), `T10Y2Y` (yield curve slope)
  - **EPU**: `USEPUINDXD` (Economic Policy Uncertainty Index) — daily
  - **Industrial production**: `INDPRO` (US), `XTEXVA01CNM667S` (China export value)
  - **Baltic Dry Index proxy**: `n/a` (nie w FRED — backup z Yahoo Finance `^BDIY` jeśli dostępny)
  - **US crude production**: `MCRFPUS2` (monthly)
  - **Global oil price**: `POILBREUSDM` (Brent monthly average)
- [ ] Wszystkie serie → `macro_indicators` tabela (z #77)
- [ ] `GET /api/v1/macro/rates` → { fed_funds, us10y, yield_curve, dxy }
- [ ] `GET /api/v1/macro/uncertainty` → { epu_current, epu_30d_avg, percentile }
- [ ] Frontend: macro indicator panel z spark charts
- [ ] Alert: yield curve inversion (T10Y2Y < 0) → alert 'recession_signal'
- [ ] Test: test_fred_macro_fetch, test_yield_curve_alert

**Pliki do stworzenia:**
- Rozszerz `backend/ingestion/fred_prices.py`
- Rozszerz `backend/api/v1/macro.py`
- `frontend/src/components/analytics/MacroIndicators.vue`

**Dependency:** #62 (FRED infrastructure), #77 (macro_indicators table)

---

### Issue #87
**Title:** `[M6] Bunker fuel price proxy — yfinance + FRED energy derivatives`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** Estymacja cen bunker fuel na podstawie darmowych proxy (heating oil futures, diesel spot).

> ⚠️ **UWAGA (audyt):** Oryginalne założenie o USDA AgTransport było błędne — USDA raportuje koszty transportu zboża, NIE ceny paliwa bunkrowego. Bunker fuel prices (IFO 380, VLSFO, MGO) to dane proprietary (Ship & Bunker, Platts). Używamy proxy z darmowych źródeł.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/bunker_fuel.py`
- [ ] Źródła proxy:
  - **yfinance** `HO=F` (heating oil futures) — najlepszy proxy dla IFO 380 / VLSFO (korelacja ~0.9)
  - **FRED** `DHOILNYH` (heating oil NY spot) — backup daily
  - **FRED** `DDFUELUSGULF` (diesel US Gulf) — proxy dla MGO
  - Przeliczenie: barrel → metric tonne (heating oil: ~7.45 bbl/mt)
- [ ] Nowa tabela `bunker_prices` (id UUID PK, fuel_type TEXT NOT NULL, price_usd_mt REAL, proxy_source TEXT, time TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ DEFAULT now())
  - fuel_type: 'ifo380_proxy', 'vlsfo_proxy', 'mgo_proxy'
- [ ] Celery Beat: co 6h (współdzielony z yfinance task — patrz nota konsolidacji)
- [ ] `GET /api/v1/analytics/bunker?fuel=vlsfo_proxy&days=30` → { prices[], avg, trend }
- [ ] Integracja z #58 (emissions): voyage fuel cost = fuel_consumption × bunker_price_proxy
- [ ] Frontend: bunker price proxy chart z wyraźnym oznaczeniem "Estimated (proxy)"
- [ ] Alert: bunker price proxy > 2σ above 90d mean → alert 'bunker_price_spike'
- [ ] Test: test_bunker_proxy_calculation, test_barrel_to_mt_conversion

**Pliki do stworzenia:**
- `backend/ingestion/bunker_fuel.py`
- `backend/migrations/versions/xxx_create_bunker_prices.py`
- `backend/api/v1/analytics.py` — rozszerz o /bunker endpoint
- `frontend/src/components/analytics/BunkerPriceChart.vue`

**Dependency:** #61 (yfinance infrastructure), #62 (FRED infrastructure)

---

### Issue #88
**Title:** `[M6] OpenSanctions expanded — 300K+ sanctioned entities`
**Labels:** `milestone-6` `backend` `data-ingestion` `compliance` `priority-high`

**Cel:** Rozszerzenie #52 (sanctions) o pełną bazę OpenSanctions — lepsza od samego OFAC.

**Acceptance criteria:**
- [ ] Rozszerzenie `backend/ingestion/sanctions.py` (z #52):
  - ⚠️ **RYZYKO PRAWNE:** OpenSanctions "free for non-commercial" — komercyjne SaaS wymaga licencji. Sprawdzić pricing na `https://www.opensanctions.org/licensing/`. Alternatywa: bezpośredni import z OFAC SDN + EU Consolidated (oba w pełni darmowe, bez ograniczeń)
  - **OpenSanctions API**: `https://api.opensanctions.org/` — wymaga licencji komercyjnej dla SaaS
  - **Fallback (darmowy):** bezpośredni OFAC SDN XML + EU Consolidated XML + UN Security Council list — pokrywa ~80% entities, zero kosztów
  - 300K+ entities z 50+ list sankcyjnych (OFAC, EU, UN, UK, Australia, Canada, etc.)
  - Vessel-specific sanctions (IMO match)
  - Company sanctions (owner/operator match z #57)
  - Country sanctions (flag state match)
- [ ] Bulk download: `https://data.opensanctions.org/datasets/latest/default/entities.ftm.json`
- [ ] Deduplication: OpenSanctions ma deduplikację wbudowaną (FollowTheMoney format)
- [ ] Enhanced matching: fuzzy name match (Levenshtein distance ≤ 2) + exact IMO match
- [ ] `GET /api/v1/compliance/sanctions/check?entity=xxx` → { sanctioned: bool, matches: [...], lists: [...] }
- [ ] Multi-list display: "Sanctioned by: OFAC SDN, EU Consolidated, UK OFSI"
- [ ] Test: test_opensanctions_import, test_fuzzy_match, test_multi_list

**Pliki do stworzenia:**
- Rozszerz `backend/ingestion/sanctions.py`
- Rozszerz `backend/api/v1/compliance.py`

**Dependency:** #52 (sanctions infrastructure)

---

### Issue #89
**Title:** `[M6] Google Trends — commodity sentiment proxy`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-low`

**Cel:** Google Trends jako realtime sentiment indicator — wzrost wyszukiwań "oil price" koreluje ze zmiennością.

**Acceptance criteria:**
- [ ] Nowy moduł `backend/ingestion/google_trends.py`
- [ ] ⚠️ **RYZYKO STABILNOŚCI:** `pytrends` to nieoficjalny wrapper — Google regularnie go blokuje, psuje się na tygodnie. Nie polegać na nim jako kluczowym źródle.
- [ ] Użycie `pytrends` (unofficial Google Trends API) — free, no key
- [ ] **Fallback:** SERPAPI Google Trends endpoint (~$50/mies) jeśli pytrends zawiedzie. Lub: pominąć ten issue jeśli pytrends zbyt niestabilny — EPU index z FRED (#86) daje podobny sygnał stabilniej
- [ ] Keywords per commodity: "oil price", "gold price", "wheat price", "gas price", "copper price", "OPEC", "sanctions Russia oil", "energy crisis"
- [ ] Celery Beat: co 6h — pobierz interest_over_time (7 dni, hourly resolution)
- [ ] Wstaw do `macro_indicators`: provider='google_trends', indicator_name='search_interest_{keyword}'
- [ ] `GET /api/v1/sentiment/trends?keywords=oil+price,gold+price&days=30` → { series: [{ keyword, interest: [{ time, value }] }] }
- [ ] Spike detection: jeśli interest > 3× 30d mean → alert 'search_spike' (wskazuje na market event)
- [ ] Frontend: trends sparklines obok commodity price chart
- [ ] `pip install pytrends` dodany do requirements.txt
- [ ] Test: test_google_trends_fetch, test_spike_detection

**Pliki do stworzenia:**
- `backend/ingestion/google_trends.py`
- Rozszerz `backend/api/v1/macro.py` (lub nowy `backend/api/v1/sentiment.py`)

**Dependency:** #77 (macro_indicators table)

---

### Issue #90
**Title:** `[M6] CPB World Trade Monitor + LME warehouse stocks`
**Labels:** `milestone-6` `backend` `data-ingestion` `priority-medium`

**Cel:** Globalne wolumeny handlu (CPB) + zapasy metali w magazynach LME — dwa niszowe ale wartościowe datasety.

**Acceptance criteria:**
- [ ] **CPB World Trade Monitor** (`backend/ingestion/cpb_trade.py`):
  - Źródło: `https://www.cpb.nl/en/world-trade-monitor` — free Excel download, monthly
  - Dane: global trade volume indices (world, advanced economies, emerging), industrial production indices
  - Wstaw do `macro_indicators`: provider='CPB'
  - `GET /api/v1/macro/world-trade` → { world_volume_index, advanced_economies, emerging, mom_change, yoy_change }
- [ ] **LME Warehouse Stocks** (`backend/ingestion/lme_stocks.py`):
  - ⚠️ **RYZYKO PRAWNE:** LME ToS explicite zabrania automated scraping. Scraping lme.com jest nielegalne.
  - **Opcja A (preferowana):** DBnomics (#77) może mieć LME warehouse data via authorized provider — zweryfikować
  - **Opcja B:** Quandl/Nasdaq Data Link — sprawdzić `CHRIS/CME_HG1` etc. dla stock proxies
  - **Opcja C:** yfinance metal ETFs (JJM, CPER) jako proxy dla metal supply indicators
  - **Opcja D (last resort):** Ręczny tygodniowy import z publicznie dostępnych raportów
  - Metale: copper, aluminium, zinc, nickel, lead, tin
  - Nowa tabela `warehouse_stocks` (id UUID PK, exchange TEXT, metal TEXT NOT NULL, tonnage REAL, time TIMESTAMPTZ NOT NULL, daily_change REAL, created_at TIMESTAMPTZ DEFAULT now())
  - Indeks: `(metal, time DESC)`
  - `GET /api/v1/analytics/warehouse?metal=copper&days=90` → { current_tonnage, trend, vs_5yr_avg }
  - Falling stocks → bullish signal, rising stocks → bearish
- [ ] Frontend: LME stocks chart z overlay na metal price
- [ ] Alert: stock decline > 10% w 30d → alert 'warehouse_drawdown'
- [ ] Test: test_cpb_fetch, test_lme_stocks_fetch

**Pliki do stworzenia:**
- `backend/ingestion/cpb_trade.py`
- `backend/ingestion/lme_stocks.py`
- `backend/migrations/versions/xxx_create_warehouse_stocks.py`
- Rozszerz `backend/api/v1/macro.py`
- Rozszerz `backend/api/v1/analytics.py`

**Dependency:** #77 (macro_indicators table)

---

## Zaktualizowany dependency graph (final v3 — post-audit)

```
M0 (fundamenty):
    #1 → #2 → #3 → #4 → #5 → #6 → #36
    #91 (alert_type expansion) ← #3
    #92 (charting library) — standalone
    #93 (design system) — standalone
    #105 (E2E Playwright) — standalone
                                        ↓
M1 (core features + UX foundation):
    #7 → #8 → #9 → #10
    #11 → #12
    #13 → #14 → #15
    #16 (launch)
    #94 (navigation) ← #93
    #95 (home dashboard) ← #92, #93, #94
    #96 (watchlist) ← #4, #17
    #97 (alert management) ← #20, #21, #91
    #98 (analytics parent view) ← #92, #94
    #100 (performance) — standalone
    #101 (loading/empty/error states) ← #93
    #102 (responsive) ← #94
                                        ↓
M2 (data + search):
    #17 → #18 → #19 → #20 → #21
    #22 → #23
    #24 → #25
    #37 (onboarding)
    #99 (global search) ← #8, #11, #17
                                        ↓
        ┌──── M3: #26 → #27 → #28 → #29 → #30 → #31
        │
M2 ─────┤
        │
        ├──── M5-A: #39 → #40 → #41 → #42 → #43 → #44 → #45
        │       │                         ↓
        │       │    M5-B: #46 → #47 → #48 → #49
        │       │            #58 (emissions) → #107 (emissions frontend)
        │       │            #60 (price alerts)
        │       │            #61 → #62 → #63 (commodity expansion)
        │       │            #64-#70 (fundamental analysis)
        │       │                         ↓
        │       │    M5-C: #50 (AI chat), #51 (export)
        │       │          #55 (weather), #56 (infrastructure)
        │       │                         ↓
        │       └──  M5-D: #52 → #53 → #54
        │                  #57 (ownership)  #59 (spoofing)
        │
        ├──── M6 (parallel, standalone data feeds):
        │     #76 (IMF PortWatch) ← #25
        │     #77 (DBnomics) → #80 (GPR), #86 (FRED macro), #89 (Google Trends), #90 (CPB)
        │     #78 (Frankfurter FX) — standalone
        │     #79 (ACLED) ← #56  ⚠️ wymaga licencji komercyjnej
        │     #81 (Baker Hughes) — standalone
        │     #82 (JODI) ← #70  ⚠️ brak programmatic API
        │     #83 (EIA expanded) ← #65
        │     #84 (USDA crops) — standalone
        │     #85 (Carbon prices) ← #58
        │     #87 (Bunker fuel proxy) ← #61, #62
        │     #88 (OpenSanctions+) ← #52  ⚠️ wymaga licencji komercyjnej
        │     #108 (missing frontend components) ← #77, #92, #98
        │
        └──── M4 (operations):
              #32 → #33 → #34 → #35 → #38 (Sentry)
              #103 (Celery monitoring) ← #38
              #104 (DB retention) ← #3
              #106 (Redis config) ← #6
              #109 (structured logging) ← #38
```

**Total: 109 issues across 7 milestones (M0-M6)**
- M0: 6 + 4 nowe (#91-#93, #105) = **10 issues**
- M1: 10 + 7 nowe (#94-#98, #100-#102) = **17 issues**
- M2: 8 + 1 nowy (#99) = **9 issues**
- M3: 6 issues
- M4: 5 + 4 nowe (#103, #104, #106, #109) = **9 issues**
- M5: 36 + 1 nowy (#107) = **37 issues**
- M6: 15 + 1 nowy (#108) = **16 issues**

**Total: 90 issues across 7 milestones (M0-M6)**

---

## Decyzja architektoniczna: Data source inventory (M6)

### Darmowe źródła danych — pełna lista (40+)

| Źródło | Typ danych | Koszt | Rate limit | Issue |
|--------|-----------|-------|------------|:-----:|
| aisstream.io | AIS positions | Free | Unlimited WS | #7 |
| yfinance | Commodity futures | Free | ~2K/h | #61 |
| FRED API | Spot prices + macro | Free (key) | 120/min | #62, #86 |
| EIA API v2 | Energy inventories + STEO | Free (key) | 100K/day | #65, #83 |
| Nasdaq Data Link | Metal/energy prices | Free tier | 50/day | #17 |
| World Bank Pink Sheet | Fertilizers + niche | Free | None | #63 |
| CFTC | COT reports | Free | None | #64 |
| GDELT | News events | Free | None | #18 |
| Open-Meteo | Weather | Free | Unlimited | #55 |
| Global Energy Monitor | Infrastructure | Free | None | #56 |
| Equasis | Vessel ownership | Free (account) | ~100/day | #57 |
| OpenSanctions | Sanctions lists | Free (non-comm) | Bulk DL | #52, #88 |
| IMF PortWatch | Port/chokepoint data | Free | API | #76 |
| DBnomics | 80+ providers (IMF, OECD) | Free | Unlimited | #77 |
| Frankfurter | FX rates | Free | Unlimited | #78 |
| ACLED | Conflict events | Free (academic) | API key | #79 |
| GPR Index | Geopolitical risk | Free | CSV DL | #80 |
| Baker Hughes | Rig counts | Free | Weekly CSV | #81 |
| JODI | Global oil S/D | Free | CSV DL | #82 |
| USDA NASS | Crop progress | Free (key) | API | #84 |
| USDA FAS | Export sales + PSD | Free (key) | API | #84 |
| USDA AgTransport | Bunker fuel prices | Free | Socrata | #87 |
| Ember Climate | Carbon prices | Free | CSV DL | #85 |
| Google Trends (pytrends) | Search sentiment | Free | ~10/min | #89 |
| CPB Netherlands | World trade volumes | Free | Monthly XLS | #90 |
| LME (delayed) | Warehouse stocks | Free (2d delay) | Scrape | #90 |

### Pokrycie docelowe po M6:
- **~55 commodities** (42 z M5 + carbon credits + bunker fuel + more metals)
- **15+ FX pairs** + DXY proxy
- **20+ macro indicators** (PMI, industrial production, interest rates, EPU, GPR)
- **Crop progress** for 4 major ag commodities
- **300K+ sanctioned entities** (50+ lists)
- **2,033 ports** z IMF data
- **6 LME metals** warehouse stocks
- **Conflict events** geocoded near infrastructure
- **90+ countries** S/D balance via JODI

---

## MILESTONE 0/1 — Brakujące issues wykryte w audycie

> Te issues powinny być zaimplementowane PRZED lub RÓWNOLEGLE z M5/M6.
> Bez nich platforma będzie miała potężny backend ale chaotyczny frontend.

---

### Issue #91
**Title:** `[M0] Expand alert_type — migrate ENUM to TEXT with CHECK constraint`
**Labels:** `milestone-0` `backend` `priority-critical` `schema`

**Cel:** Rozszerzenie `alert_type` z 5 wartości do 25+ — wymagane przez wszystkie M5/M6 alerty.

**Acceptance criteria:**
- [ ] Alembic migration:
  ```sql
  ALTER TABLE alert_events ALTER COLUMN type TYPE TEXT;
  ALTER TABLE alert_events ADD CONSTRAINT alert_type_check CHECK (type IN (...));
  ```
- [ ] Lista dozwolonych typów (patrz decyzja architektoniczna wyżej — 28 typów)
- [ ] Backward compatible — istniejące dane zachowane
- [ ] Test: test_new_alert_type_insertable, test_invalid_type_rejected

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_expand_alert_type.py`

**Dependency:** #3 (schema setup)

---

### Issue #92
**Title:** `[M0] Select charting library + create BaseChart components`
**Labels:** `milestone-0` `frontend` `priority-critical` `design-system`

**Cel:** Jedna biblioteka chartingowa dla WSZYSTKICH 20+ chart components. Bez tego każdy chart będzie inny.

**Acceptance criteria:**
- [ ] Wybór biblioteki: **Apache ECharts** (rekomendacja — najlepsza dla financial data: heatmapy, candlesticks, overlays, duże datasety)
  - Alternatywa: Lightweight Charts (TradingView OSS) — świetny dla time series, ale brak heatmap
- [ ] `npm install echarts vue-echarts`
- [ ] Shared components:
  - `frontend/src/components/charts/BaseTimeSeriesChart.vue` — props: data, timeRange, overlays, bands, yAxis config
  - `frontend/src/components/charts/BaseHeatmap.vue` — for correlation matrix (#67)
  - `frontend/src/components/charts/BaseCandlestick.vue` — for OHLC price data
  - `frontend/src/components/charts/BaseBarChart.vue` — for COT, inventories, S/D balance
- [ ] Standardowy `TimeRangeSelector.vue`: 1D / 1W / 1M / 3M / 6M / 1Y / 5Y / ALL
- [ ] Standardowy tooltip format: date, value, % change, source
- [ ] Responsive: charts resize na window resize
- [ ] Dark mode support (przygotowanie na przyszłość)
- [ ] Chart data downsampling util: jeśli >1000 points → downsample do ~500 (LTTB algorithm)
- [ ] Test: test_chart_renders, test_time_range_selector

**Pliki do stworzenia:**
- `frontend/src/components/charts/BaseTimeSeriesChart.vue`
- `frontend/src/components/charts/BaseHeatmap.vue`
- `frontend/src/components/charts/BaseCandlestick.vue`
- `frontend/src/components/charts/BaseBarChart.vue`
- `frontend/src/components/charts/TimeRangeSelector.vue`
- `frontend/src/utils/chart-downsample.ts`

**Dependency:** Brak (M0 — fundamenty)

---

### Issue #93
**Title:** `[M0] Design system — shared UI components`
**Labels:** `milestone-0` `frontend` `priority-critical` `design-system`

**Cel:** Spójny design across all dashboards. Bez tego każdy view będzie wyglądał inaczej.

**Acceptance criteria:**
- [ ] Wybór UI framework: **PrimeVue** lub **Naive UI** (rekomendacja: PrimeVue — DataTable, drzewa, kalendarze out of the box)
  - Alternatywa: Headless UI + Tailwind (więcej customizacji, więcej pracy)
- [ ] Shared components:
  - `DataTable.vue` — sortable, filterable, exportable (CSV), paginated, virtual scroll for >1000 rows
  - `StatCard.vue` — value + change (%) + sparkline + label + icon
  - `FilterBar.vue` — commodity selector, region selector, date range picker
  - `DetailPanel.vue` — slide-out right panel pattern (for vessel detail, port detail, etc.)
  - `LoadingSkeleton.vue` — placeholder during API calls
  - `EmptyState.vue` — "Dane jeszcze się akumulują" + progress indicator + ETA
  - `ErrorState.vue` — "Nie udało się pobrać danych" + retry button
  - `Badge.vue` — status badges (laden/ballast, risk levels, etc.)
- [ ] Color palette: consistent teal/blue (commodities), red (alerts), green (positive), gray (neutral)
- [ ] Typography: consistent font sizes for headings, body, captions, numbers
- [ ] Spacing: 4px grid system
- [ ] Test: component storybook lub test renders

**Pliki do stworzenia:**
- `frontend/src/components/ui/DataTable.vue`
- `frontend/src/components/ui/StatCard.vue`
- `frontend/src/components/ui/FilterBar.vue`
- `frontend/src/components/ui/DetailPanel.vue`
- `frontend/src/components/ui/LoadingSkeleton.vue`
- `frontend/src/components/ui/EmptyState.vue`
- `frontend/src/components/ui/ErrorState.vue`
- `frontend/src/components/ui/Badge.vue`
- `frontend/src/styles/design-tokens.css`

**Dependency:** Brak (M0 — fundamenty)

---

### Issue #94
**Title:** `[M1] App navigation layout — sidebar + route hierarchy`
**Labels:** `milestone-1` `frontend` `priority-critical` `design-system`

**Cel:** Główna nawigacja platformy. 10+ dashboards potrzebuje jasnej hierarchii.

**Acceptance criteria:**
- [ ] `AppLayout.vue` z collapsible left sidebar:
  - **Map** — Live tracking (default view)
  - **Commodities** — Prices, flows, charts
  - **Analytics** (expandable):
    - COT (#64), Inventories (#65), Crack Spreads (#66)
    - Correlations (#67), Seasonal (#68), Forward Curves (#69)
    - S/D Balance (#70), Rig Count (#81)
  - **Macro** (expandable):
    - PMI/Industrial (#77), FX & DXY (#78), Rates (#86)
    - GPR (#80), World Trade (#90)
  - **Energy** (expandable):
    - Nat Gas Storage (#83), SPR (#83), Bunker Fuel (#87), Carbon (#85)
  - **Agriculture** (expandable):
    - Crop Progress (#84), WASDE (#70)
  - **Fleet & Ports** — Fleet (#71), Port Analytics (#72)
  - **Compliance** — Sanctions, AIS Gaps, STS, Spoofing
  - **Simulation** — Run/view simulations
  - **Events** — Historical replay (#74)
  - **Settings** — Profile, billing, API keys, notifications
- [ ] Vue Router config z lazy loading per route (code splitting)
- [ ] Sidebar collapse na mobile → hamburger menu
- [ ] Active route highlighting
- [ ] Breadcrumbs for nested views
- [ ] Keyboard shortcut: `Cmd+K` → global search (patrz #99)
- [ ] Test: test_navigation_renders, test_route_lazy_loading

**Pliki do stworzenia:**
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/layouts/Sidebar.vue`
- `frontend/src/layouts/Breadcrumbs.vue`
- Refactor `frontend/src/router/index.ts` z lazy imports

**Dependency:** #93 (design system)

---

### Issue #95
**Title:** `[M1] Home Dashboard — aggregated overview`
**Labels:** `milestone-1` `frontend` `priority-critical`

**Cel:** Strona główna po zalogowaniu — podsumowanie najważniejszych informacji. Bez tego użytkownik nie wie gdzie zacząć.

**Acceptance criteria:**
- [ ] Grid layout:
  - **Top row (4x StatCard):** Top Mover commodity (% change), Active Alerts count, Vessels Tracked count, Watchlist summary
  - **Row 2 (2 columns):**
    - Left: Watchlist sparklines (user's commodities z cenami + mini chart)
    - Right: Recent Alerts (top 5, color-coded by severity)
  - **Row 3 (2 columns):**
    - Left: Active Voyages count by commodity (donut chart)
    - Right: News Feed (latest 5 GDELT events)
  - **Row 4 (full width):**
    - Market Overview: heat map of commodity daily changes (green/red tiles, like finviz.com)
- [ ] Personalized: shows user's watchlist commodities prominently
- [ ] Auto-refresh: StatCards update via SSE every 60s
- [ ] Loading skeletons while data loads
- [ ] Empty states: "Add commodities to your watchlist" prompt for new users
- [ ] Test: test_dashboard_renders

**Pliki do stworzenia:**
- `frontend/src/views/HomeDashboard.vue`
- `frontend/src/components/dashboard/MarketHeatmap.vue`
- `frontend/src/components/dashboard/WatchlistPanel.vue`
- `frontend/src/components/dashboard/RecentAlerts.vue`
- `frontend/src/stores/useDashboardStore.ts`

**Dependency:** #92 (charts), #93 (UI components), #94 (navigation)

---

### Issue #96
**Title:** `[M1] Watchlist / Favorites system`
**Labels:** `milestone-1` `backend` `frontend` `priority-high`

**Cel:** Użytkownik wybiera 5-15 commodities do śledzenia. Filtruje cały UI pod jego potrzeby.

**Acceptance criteria:**
- [ ] Tabela `user_watchlist` (id UUID PK, user_id TEXT NOT NULL, commodity commodity_type NOT NULL, added_at TIMESTAMPTZ DEFAULT now(), UNIQUE(user_id, commodity))
- [ ] `POST /api/v1/watchlist` → { commodity: "crude_oil" }
- [ ] `DELETE /api/v1/watchlist/{commodity}`
- [ ] `GET /api/v1/watchlist` → [{ commodity, latest_price, daily_change_pct, sparkline_7d }]
- [ ] Frontend: "Add to Watchlist" star icon on every commodity card/chart
- [ ] Home Dashboard (#95) uses watchlist as primary data source
- [ ] Alert subscriptions (#21) auto-created for watchlist commodities
- [ ] Onboarding (#37): role selection suggests default watchlist:
  - Energy trader: crude_oil, lng, gasoline, diesel, heating_oil
  - Metals: gold, silver, copper, aluminium, iron_ore
  - Agriculture: wheat, corn, soybeans, coffee, sugar
  - General: crude_oil, gold, copper, wheat, lng
- [ ] Test: test_watchlist_crud, test_watchlist_with_prices

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_create_user_watchlist.py`
- `backend/api/v1/watchlist.py`
- `frontend/src/components/ui/WatchlistStar.vue`
- `frontend/src/stores/useWatchlistStore.ts`

**Dependency:** #4 (auth), #17 (commodity_prices)

---

### Issue #97
**Title:** `[M1] Alert management system — priority, digest, grouping`
**Labels:** `milestone-1` `backend` `frontend` `priority-critical`

**Cel:** Bez tego systemu użytkownik dostanie 30-130+ alertów/dzień i wyłączy wszystkie powiadomienia.

**Acceptance criteria:**
- [ ] **Priority tiers:**
  - P1 CRITICAL: natychmiast push (sanctions match, price 3σ spike, AIS spoofing) — max 5/dzień
  - P2 WARNING: batch co godzinę (price 2σ, correlation break, inventory surprise) — max 20/dzień
  - P3 INFO: daily digest only (seasonal anomaly, search spike, rig count change) — unlimited
- [ ] **Alert grouping:** "5 energy price alerts" zamiast 5 osobnych notyfikacji
- [ ] **Daily digest email:** 07:00 local timezone — summary of all P2/P3 alerts from last 24h
  - Subject: "SupplyShock Daily Brief — 3 price alerts, 2 compliance flags, 1 inventory surprise"
  - HTML template z sekcjami per category
- [ ] **Alert center frontend:** dedicated view w sidebar
  - Lista alertów z filtrami: type, priority, read/unread, date range
  - Bulk actions: mark all as read, mute type for 24h/7d/forever
  - Snooze button per alert (1h, 4h, 24h, 7d)
  - "Quiet hours" setting: np. 22:00-07:00 — no push notifications
- [ ] **Mute/unmute per alert type:** user can disable entire categories
- [ ] Rozszerzenie tabeli `alert_events`: ADD COLUMNS `priority TEXT DEFAULT 'info'`, `read BOOLEAN DEFAULT false`, `snoozed_until TIMESTAMPTZ`
- [ ] `GET /api/v1/alerts?unread=true&priority=critical` — filtered alert feed
- [ ] `PATCH /api/v1/alerts/{id}/read`
- [ ] `PATCH /api/v1/alerts/{id}/snooze?until=2026-03-17T07:00:00Z`
- [ ] Test: test_alert_priority_assignment, test_digest_email, test_snooze

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_extend_alert_events.py`
- `backend/notifications/digest.py`
- `backend/api/v1/alerts.py` — rozszerz
- `frontend/src/views/AlertCenter.vue`
- `frontend/src/stores/useAlertStore.ts`
- Email template: `backend/templates/daily_digest.html`

**Dependency:** #20 (SSE alerts), #21 (subscriptions), #91 (alert_type expansion)

---

### Issue #98
**Title:** `[M1] Analytics parent view — sub-navigation for 8+ chart types`
**Labels:** `milestone-1` `frontend` `priority-high`

**Cel:** Jeden widok "Analytics" z tabbed/sidebar navigation do COT, inventories, cracks, correlations, seasonal, forward curves, S/D, rig count.

**Acceptance criteria:**
- [ ] `AnalyticsDashboard.vue` — parent view z:
  - Horizontal tab bar lub left sub-nav: COT | Inventories | Crack Spreads | Correlations | Seasonal | Forward Curves | S/D Balance | Rig Count
  - Każdy tab lazy-loaded (dynamic import)
  - Shared commodity selector na górze — zmiana commodity zmienia dane we WSZYSTKICH tabs
  - Time range selector (shared) — applies to all charts
- [ ] URL routing: `/analytics/cot`, `/analytics/inventories`, `/analytics/correlations`, etc.
- [ ] Default tab: COT (najczęściej używany)
- [ ] Responsive: tabs → dropdown na mobile
- [ ] Test: test_analytics_tab_navigation

**Pliki do stworzenia:**
- `frontend/src/views/AnalyticsDashboard.vue`
- `frontend/src/router/analytics.ts` — sub-routes

**Dependency:** #92 (charts), #94 (navigation)

---

### Issue #99
**Title:** `[M2] Global search (Cmd+K) — search across all entities`
**Labels:** `milestone-2` `backend` `frontend` `priority-high`

**Cel:** Użytkownik wpisuje "Suez" i widzi chokepoint data, alerty, voyages, news. Wpisuje "VLCC" i widzi statki.

**Acceptance criteria:**
- [ ] `Cmd+K` (Mac) / `Ctrl+K` (Windows) → modal search overlay
- [ ] Backend: `GET /api/v1/search?q=suez&limit=10` → categorized results:
  - Vessels: match by name, IMO, MMSI
  - Ports: match by name, UNLOCODE, country
  - Commodities: match by name, ticker
  - Chokepoints: match by name
  - Fleet owners: match by company name
  - Historical events: match by name, description
- [ ] Frontend: instant search (debounced 300ms), results grouped by category with icons
- [ ] Keyboard navigation: arrow keys to navigate, Enter to select
- [ ] Recent searches: last 5 queries saved in localStorage
- [ ] pg_trgm for fuzzy matching (already enabled in schema)
- [ ] Test: test_search_vessels, test_search_fuzzy, test_search_keyboard_nav

**Pliki do stworzenia:**
- `backend/api/v1/search.py`
- `frontend/src/components/ui/GlobalSearch.vue`

**Dependency:** #8 (vessels), #11 (ports), #17 (commodities)

---

### Issue #100
**Title:** `[M1] Frontend performance foundation — code splitting, virtualization`
**Labels:** `milestone-1` `frontend` `priority-high` `performance`

**Cel:** Z 20+ chart components, 6+ map layers, i 10+ views — bundle i runtime muszą być zoptymalizowane.

**Acceptance criteria:**
- [ ] **Code splitting:** Vue Router lazy imports dla wszystkich views (dynamic `() => import(...)`)
- [ ] **Bundle analysis:** `vite-plugin-visualizer` — verify no single chunk > 200KB
- [ ] **Virtual scrolling:** użyj `vue-virtual-scroller` dla tabel >100 rows (vessels, voyages, alerts, sanctions)
- [ ] **Chart downsampling API param:** `?resolution=daily|hourly|raw` — backend returns max 500 points per chart
- [ ] **Map optimization:**
  - Vessel clustering at zoom < 8 (MapLibre/Deck.gl cluster layer)
  - Layer visibility by zoom level: infrastructure only at zoom > 5, conflicts only at zoom > 6
  - Max 3 overlay layers active simultaneously (toggle others off)
- [ ] **Image lazy loading:** `loading="lazy"` for all non-critical images
- [ ] **SSE connection management:** max 2 concurrent SSE streams, reconnect with exponential backoff
- [ ] **Web Worker:** offload correlation matrix computation (#67) to a Web Worker
- [ ] Test: Lighthouse performance score > 70 on home dashboard

**Pliki do stworzenia:**
- `frontend/src/utils/virtual-scroll.ts`
- `frontend/vite.config.ts` — update z chunk splitting strategy
- `frontend/src/workers/correlation-worker.ts`

**Dependency:** Brak (M1 — fundamenty)

---

### Issue #101
**Title:** `[M1] Loading, empty, and error state components`
**Labels:** `milestone-1` `frontend` `priority-high` `design-system`

**Cel:** Każdy dashboard musi obsługiwać 3 stany: ładowanie, brak danych, błąd.

**Acceptance criteria:**
- [ ] `LoadingSkeleton.vue` — animowane placeholdery (pulse animation) dla:
  - Chart placeholder (rectangle with gradient)
  - Table placeholder (rows with gray bars)
  - StatCard placeholder
  - Map placeholder
- [ ] `EmptyState.vue` — kontekstowy komunikat z ikoną:
  - Seasonal chart bez 2 lat danych: "Analiza sezonowa wymaga 2 lat historii cenowej. Dostępne: {days} dni. Pełna analiza ~{ETA}."
  - COT bez piątkowego importu: "Dane COT aktualizowane w piątki 22:00 UTC. Następna aktualizacja: {date}."
  - Watchlist pusta: "Dodaj commodities do watchlisty klikając ★ przy nazwie."
  - Brak voyages: "Detekcja voyages wymaga ~2 tygodni zbierania danych AIS."
- [ ] `ErrorState.vue` — ikona + komunikat + retry button:
  - API error: "Nie udało się pobrać danych. [Spróbuj ponownie]"
  - External source down: "Źródło danych (yfinance) niedostępne. Ostatnie dane: {timestamp}."
- [ ] `DataFreshnessIndicator.vue` — małe badge "Updated 5 min ago" / "Stale (2h ago)" z kolorem
- [ ] Każdy chart/dashboard component opakowuje dane w `<LoadingSkeleton v-if="loading">` / `<EmptyState v-else-if="empty">` / `<ErrorState v-else-if="error">` / `<ActualContent v-else>`

**Pliki do stworzenia:**
- `frontend/src/components/ui/LoadingSkeleton.vue`
- `frontend/src/components/ui/EmptyState.vue`
- `frontend/src/components/ui/ErrorState.vue`
- `frontend/src/components/ui/DataFreshnessIndicator.vue`
- `frontend/src/composables/useDataState.ts` — shared composable for loading/error/empty logic

**Dependency:** #93 (design system)

---

### Issue #102
**Title:** `[M1] Responsive layout foundation`
**Labels:** `milestone-1` `frontend` `priority-medium` `design-system`

**Cel:** Podstawowa responsywność — nie mobile-first, ale dashboard nie może się rozjechać na tablecie/laptopie.

**Acceptance criteria:**
- [ ] Breakpoints: `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`, `2xl: 1536px`
- [ ] Sidebar: collapsed on < lg, hamburger menu on < md
- [ ] Chart grids: 2-column on xl, 1-column on < lg
- [ ] DataTable: horizontal scroll on < lg (nie łamać kolumn)
- [ ] Map: full width on all sizes, controls repositioned on mobile
- [ ] StatCards: 4-grid → 2-grid → 1-grid responsive
- [ ] Test: visual test at 1920px, 1366px, 768px widths

**Pliki do stworzenia:**
- `frontend/src/styles/responsive.css`
- Update `frontend/src/layouts/AppLayout.vue`

**Dependency:** #94 (navigation layout)

---

## MILESTONE operations — Infrastruktura operacyjna

---

### Issue #103
**Title:** `[M4] Celery monitoring + worker scaling strategy`
**Labels:** `milestone-4` `backend` `infrastructure` `priority-high`

**Cel:** 35+ Celery Beat tasks wymaga monitoringu i proper worker configuration.

**Acceptance criteria:**
- [ ] **Celery Flower** deployment: `pip install flower`, dostępny na `/flower/` (za auth)
- [ ] **Task queues** (3 kolejki):
  - `ais` — AIS stream processing, voyage detection, spoofing detection (high priority, dedicated worker)
  - `ingestion` — all external data ingestion tasks (FRED, yfinance, EIA, etc.) (medium priority)
  - `analytics` — correlation matrix, crack spreads, port analytics, price anomalies (low priority, CPU-heavy)
- [ ] **Worker config:**
  - Worker 1: `celery -A backend.simulation.tasks worker -Q ais -c 2` (2 concurrent tasks)
  - Worker 2: `celery -A backend.simulation.tasks worker -Q ingestion -c 4` (4 concurrent tasks)
  - Worker 3: `celery -A backend.simulation.tasks worker -Q analytics -c 2` (2 concurrent, CPU-bound)
- [ ] **Task failure alerting:** Sentry integration (#38) + custom alert if task fails 3x consecutively
- [ ] **Stale data detection:** Celery task `check_data_freshness` co 30 min:
  - Sprawdź `MAX(created_at)` per table (vessel_positions, commodity_prices, etc.)
  - Jeśli data starsza niż 2× expected interval → alert 'data_stale'
- [ ] **Task timeout:** max 5 min per ingestion task, max 10 min per analytics task
- [ ] docker-compose.yml: 3 worker services
- [ ] Test: test_task_routing, test_stale_detection

**Pliki do stworzenia:**
- `backend/monitoring/data_freshness.py`
- Update `docker-compose.yml` — 3 worker services + flower
- `backend/celeryconfig.py` — queue routing

**Dependency:** #38 (Sentry)

---

### Issue #104
**Title:** `[M4] Database retention policies + compression`
**Labels:** `milestone-4` `backend` `infrastructure` `priority-high`

**Cel:** Bez retention policies DB urośnie do ~2TB/rok. TimescaleDB compression + retention to must-have.

**Acceptance criteria:**
- [ ] **Retention policies:**
  - `vessel_positions`: 90 dni (już w planie #10)
  - `port_analytics`: 365 dni
  - `chokepoint_status`: 180 dni
  - `chokepoint_transits`: 730 dni (2 lata)
  - `eia_inventories`: keep forever (reference data, small volume)
  - `commodity_prices`: keep forever (small volume, ~15K rows/year)
  - `alert_events`: 365 dni (archive older to cold storage)
  - `conflict_events`: 730 dni
  - `bunker_prices`: 730 dni
  - `fx_rates`: keep forever (small volume)
  - `audit_log`: 365 dni
- [ ] **TimescaleDB compression:**
  - `vessel_positions`: compress after 7 days (biggest table)
  - `port_analytics`: compress after 30 days
  - `chokepoint_transits`: compress after 90 days
  - Kompresja ~10x — 2TB → ~200GB
- [ ] **Continuous aggregates:**
  - `vessel_positions` → `vessel_positions_hourly` (avg lat/lon/speed per hour per mmsi)
  - `commodity_prices` → `commodity_prices_daily` (OHLC per day)
- [ ] Celery task `apply_retention_policies` — co 24h, usuwaj dane starsze niż policy
- [ ] Monitoring: disk usage alert jeśli > 80%
- [ ] Test: test_retention_applied, test_compression_ratio

**Pliki do stworzenia:**
- `backend/migrations/versions/xxx_add_retention_policies.py`
- `backend/monitoring/disk_usage.py`
- SQL: `SELECT add_compression_policy(...)`, `SELECT add_retention_policy(...)`

**Dependency:** #3 (TimescaleDB setup)

---

### Issue #105
**Title:** `[M0] E2E test framework — Playwright setup`
**Labels:** `milestone-0` `frontend` `testing` `priority-medium`

**Cel:** Zero automated frontend tests w całym planie. Playwright jako E2E framework.

**Acceptance criteria:**
- [ ] `npm install -D @playwright/test`
- [ ] Config: `playwright.config.ts` — Chromium only (fastest), base URL = localhost:5173
- [ ] Test fixtures: authenticated user session (via Clerk test token)
- [ ] Smoke tests (5 basic):
  - Homepage loads without errors
  - Map view renders with at least 1 vessel marker
  - Commodity dashboard shows price cards
  - Login/logout flow works
  - Navigation sidebar has all expected links
- [ ] CI integration: `npx playwright test` in GitHub Actions (#35)
- [ ] Screenshot on failure for debugging
- [ ] Test: the 5 smoke tests pass in CI

**Pliki do stworzenia:**
- `frontend/playwright.config.ts`
- `frontend/tests/e2e/smoke.spec.ts`
- `frontend/tests/e2e/auth.setup.ts`
- `.github/workflows/e2e.yml`

**Dependency:** #1 (repo structure), #35 (CI/CD)

---

### Issue #106
**Title:** `[M4] Redis configuration + key namespace documentation`
**Labels:** `milestone-4` `backend` `infrastructure` `priority-medium`

**Cel:** Redis używany w 6+ modułach bez spójnej strategii zarządzania pamięcią.

**Acceptance criteria:**
- [ ] Key namespace convention:
  - `vessel:{mmsi}:*` — vessel state (last_port, last_position)
  - `cache:correlation:{window}` — correlation matrix cache (1h TTL)
  - `cache:weather:{lat}:{lon}` — weather cache (15min TTL)
  - `ratelimit:{user_id}:*` — API rate limit counters
  - `sse:{channel}:*` — SSE pub/sub channels
  - `task:lock:{task_name}` — distributed lock for Celery tasks
- [ ] `maxmemory-policy`: `allkeys-lru` (evict least recently used when memory full)
- [ ] `maxmemory`: 512MB (monitoring alert at 80%)
- [ ] TTL audit: every key MUST have TTL (no keys without expiry)
- [ ] Redis memory usage monitoring: Celery task `check_redis_memory` co 15 min
- [ ] Document in `backend/REDIS.md`
- [ ] Test: test_key_namespace_convention, test_ttl_set

**Pliki do stworzenia:**
- `backend/REDIS.md`
- `backend/monitoring/redis_health.py`
- Update `infra/redis.conf`

**Dependency:** #6 (rate limiting setup)

---

### Issue #107
**Title:** `[M5-B] Emissions dashboard frontend`
**Labels:** `milestone-5` `frontend` `priority-medium`

**Cel:** Issue #58 tworzy backend dla emissions ale NIE MA frontend component. Carbon emissions to selling point vs Argus.

**Acceptance criteria:**
- [ ] `EmissionsDashboard.vue`:
  - Total emissions per commodity route (bar chart)
  - Per-voyage emissions breakdown (table: voyage, CO2 tonnes, fuel tonnes, CII rating)
  - CII rating distribution (pie chart: A/B/C/D/E)
  - Emissions trend (line chart: monthly CO2 by commodity)
- [ ] Integration z #85 (carbon prices): **Emission Cost** = CO2 × carbon_price → "This voyage emitted 450t CO2 @ €85/t = €38,250 carbon cost"
- [ ] Filterbar: commodity, vessel type, date range
- [ ] Export: CSV with emissions data per voyage
- [ ] Test: test_emissions_dashboard_renders

**Pliki do stworzenia:**
- `frontend/src/views/EmissionsDashboard.vue`
- `frontend/src/stores/useEmissionsStore.ts`

**Dependency:** #58 (emissions backend), #85 (carbon prices), #92 (charts)

---

### Issue #108
**Title:** `[M6] Missing frontend components for data sources`
**Labels:** `milestone-6` `frontend` `priority-medium`

**Cel:** Issues #80, #82, #89, #90 mają backend endpoints ale brakuje dedykowanych frontend components.

**Acceptance criteria:**
- [ ] **GPR chart** (#80): `GPRChart.vue` — GPR index overlay na commodity price chart, dodany jako tab w MacroDashboard
- [ ] **JODI country comparison** (#82): `JODICountryChart.vue` — stacked bar per country (production/consumption/stocks), dodany jako tab w AnalyticsDashboard
- [ ] **Google Trends sparklines** (#89): `TrendsSparklines.vue` — mini sparkline widget obok commodity name (jeśli #89 zaimplementowany)
- [ ] **CPB World Trade chart** (#90): `WorldTradeChart.vue` — line chart z global/advanced/emerging indices, dodany do MacroDashboard
- [ ] **LME Warehouse chart** (#90): `WarehouseStocksChart.vue` — bar chart per metal z overlay na metal price, dodany do AnalyticsDashboard
- [ ] Wszystkie używają BaseChart components z #92

**Pliki do stworzenia:**
- `frontend/src/components/analytics/GPRChart.vue`
- `frontend/src/components/analytics/JODICountryChart.vue`
- `frontend/src/components/analytics/TrendsSparklines.vue`
- `frontend/src/components/analytics/WorldTradeChart.vue`
- `frontend/src/components/analytics/WarehouseStocksChart.vue`

**Dependency:** #77 (MacroDashboard), #92 (BaseChart), #98 (AnalyticsDashboard)

---

### Issue #109
**Title:** `[M4] Structured logging + ingestion health dashboard`
**Labels:** `milestone-4` `backend` `infrastructure` `priority-medium`

**Cel:** 35+ background tasks bez structured logging = debugging hell.

**Acceptance criteria:**
- [ ] `structlog` library: JSON formatted logs
- [ ] Standard log fields per ingestion task: `task_name`, `source`, `records_fetched`, `records_inserted`, `duration_ms`, `status`
- [ ] Log levels: DEBUG (raw data), INFO (task success), WARNING (partial failure), ERROR (task crash)
- [ ] Ingestion health endpoint: `GET /api/v1/admin/ingestion-health` (admin only):
  - Per source: last_success, last_error, records_last_24h, avg_duration, status (healthy/stale/error)
- [ ] Frontend: admin panel tab "Data Sources" — table z health status per source, red/green badges
- [ ] `pip install structlog` dodany do requirements.txt
- [ ] Test: test_structured_log_format, test_ingestion_health_endpoint

**Pliki do stworzenia:**
- `backend/logging_config.py`
- `backend/api/v1/admin.py` — ingestion health endpoint
- `frontend/src/components/admin/IngestionHealth.vue`

**Dependency:** #38 (Sentry)
