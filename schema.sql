-- ============================================================
-- SupplyShock — Database Schema
-- PostgreSQL 16 + TimescaleDB 2.x
--
-- Rules:
--   - Time-series tables are TimescaleDB hypertables
--   - Relational tables are plain PostgreSQL
--   - All tables have created_at / updated_at
--   - UUIDs as primary keys (gen_random_uuid())
--   - Never modify this file directly in production
--     → use Alembic migrations instead
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for text search on vessel names

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE plan_type AS ENUM ('free', 'pro', 'business', 'enterprise');
CREATE TYPE subscription_status AS ENUM ('active', 'past_due', 'canceled', 'trialing');
CREATE TYPE simulation_status AS ENUM ('queued', 'running', 'completed', 'failed', 'timeout');
CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'critical');
CREATE TYPE alert_type AS ENUM ('ais_anomaly', 'price_move', 'news_event', 'port_congestion', 'geopolitical');
CREATE TYPE commodity_type AS ENUM ('crude_oil', 'lng', 'coal', 'iron_ore', 'copper', 'wheat', 'soybeans', 'aluminium', 'nickel', 'palladium');
CREATE TYPE vessel_type AS ENUM ('tanker', 'bulk_carrier', 'container', 'lng_carrier', 'general_cargo', 'other');
CREATE TYPE report_status AS ENUM ('generating', 'ready', 'failed');

-- ============================================================
-- USERS & AUTH
-- (Clerk is source of truth for auth — this mirrors user data
--  for fast queries without hitting Clerk API every request)
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id   TEXT UNIQUE NOT NULL,       -- Clerk's user ID (sub claim in JWT)
    email           TEXT UNIQUE NOT NULL,
    name            TEXT,
    avatar_url      TEXT,
    plan            plan_type NOT NULL DEFAULT 'free',
    plan_expires_at TIMESTAMPTZ,                -- NULL = lifetime / not applicable
    stripe_customer_id TEXT UNIQUE,             -- set after first Stripe interaction
    -- IMPORTANT: Do NOT use simulations_used_this_month for limit enforcement.
    -- Instead, count with: SELECT COUNT(*) FROM simulations WHERE user_id=? AND
    -- created_at >= date_trunc('month', NOW()). This never needs resetting and
    -- is always accurate. This column is kept for display only (cached count).
    simulations_used_this_month INT NOT NULL DEFAULT 0,
    last_seen_at    TIMESTAMPTZ,
    -- Onboarding checklist state (Issue #37)
    -- Keys: 'explore_map', 'first_simulation', 'setup_alert'
    onboarding_completed_steps JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_clerk_id ON users(clerk_user_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe ON users(stripe_customer_id);

-- ============================================================
-- SUBSCRIPTIONS
-- (mirrors Stripe subscription state)
-- ============================================================

CREATE TABLE subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_subscription_id  TEXT UNIQUE,
    stripe_price_id         TEXT,
    plan                    plan_type NOT NULL,
    status                  subscription_status NOT NULL DEFAULT 'active',
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    cancel_at_period_end    BOOLEAN NOT NULL DEFAULT FALSE,
    canceled_at             TIMESTAMPTZ,
    trial_end               TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe ON subscriptions(stripe_subscription_id);

-- ============================================================
-- API KEYS
-- (for Pro/Business/Enterprise API access)
-- ============================================================

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        TEXT UNIQUE NOT NULL,   -- SHA-256 of actual key — never store plaintext
    key_prefix      TEXT NOT NULL,          -- first 8 chars for display: "sk_live_ab12..."
    name            TEXT NOT NULL,          -- user-given name: "My trading bot"
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,            -- NULL = no expiry
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- ============================================================
-- PORTS
-- (seeded from World Port Index — NOAA)
-- ============================================================

CREATE TABLE ports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wpi_number      INT UNIQUE,             -- World Port Index number
    name            TEXT NOT NULL,
    country_code    TEXT NOT NULL,          -- ISO 3166-1 alpha-2
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    region          TEXT,                   -- e.g. "Asia", "Europe"
    harbor_type     TEXT,                   -- from WPI: OPEN_ROADSTEAD, COASTAL_BREAKWATER etc.
    max_vessel_size TEXT,                   -- VLCC, PANAMAX, HANDYMAX, etc.
    commodities     TEXT[],                 -- array: ['coal','iron_ore']
    annual_throughput_mt DECIMAL(12,2),     -- million tonnes per year, may be NULL
    is_major        BOOLEAN NOT NULL DEFAULT FALSE,
    is_chokepoint   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ports_country ON ports(country_code);
CREATE INDEX idx_ports_coords ON ports USING GIST (
    point(longitude, latitude)
) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- ============================================================
-- TRADE FLOWS
-- (seeded from UN Comtrade — updated monthly)
-- ============================================================

CREATE TABLE trade_flows (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commodity           commodity_type NOT NULL,
    origin_country      TEXT NOT NULL,      -- ISO 3166-1 alpha-2
    destination_country TEXT NOT NULL,
    origin_port_id      UUID REFERENCES ports(id),
    destination_port_id UUID REFERENCES ports(id),
    volume_mt           DECIMAL(14,2),      -- metric tonnes
    value_usd           DECIMAL(18,2),      -- USD
    period_year         INT NOT NULL,
    period_month        INT,                -- NULL = annual figure
    source              TEXT NOT NULL DEFAULT 'un_comtrade',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trade_flows_commodity ON trade_flows(commodity);
CREATE INDEX idx_trade_flows_period ON trade_flows(period_year, period_month);
CREATE INDEX idx_trade_flows_route ON trade_flows(origin_country, destination_country);

-- ============================================================
-- VESSEL POSITIONS  [TimescaleDB hypertable]
-- (high-frequency AIS inserts — ~50k positions/minute at full scale)
-- ============================================================

CREATE TABLE vessel_positions (
    time            TIMESTAMPTZ NOT NULL,
    mmsi            BIGINT NOT NULL,        -- Maritime Mobile Service Identity
    imo             BIGINT,                 -- IMO number (more stable than MMSI)
    vessel_name     TEXT,
    vessel_type     vessel_type NOT NULL DEFAULT 'other',
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    speed_knots     DECIMAL(5,2),
    course          DECIMAL(6,2),           -- degrees true
    heading         DECIMAL(6,2),
    destination     TEXT,
    eta             TIMESTAMPTZ,
    draught         DECIMAL(5,2),           -- metres
    flag_country    TEXT,                   -- ISO 3166-1 alpha-2
    cargo_type      TEXT,                   -- AIS cargo type code
    source          TEXT NOT NULL DEFAULT 'aisstream'
);

-- Convert to hypertable, partition by week
SELECT create_hypertable('vessel_positions', 'time',
    chunk_time_interval => INTERVAL '1 week');

-- Retention policy: keep 90 days of raw positions
SELECT add_retention_policy('vessel_positions',
    INTERVAL '90 days');

-- Compression: compress chunks older than 7 days
ALTER TABLE vessel_positions SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'mmsi'
);
SELECT add_compression_policy('vessel_positions',
    INTERVAL '7 days');

CREATE INDEX idx_vp_mmsi_time ON vessel_positions(mmsi, time DESC);
-- NOTE: No partial index with WHERE time > NOW() — that predicate is evaluated
-- once at CREATE INDEX time and becomes stale immediately. TimescaleDB chunk
-- exclusion handles time filtering automatically via the hypertable partitioning.
CREATE INDEX idx_vp_coords ON vessel_positions(longitude, latitude, time DESC);

-- ============================================================
-- COMMODITY PRICES  [TimescaleDB hypertable]
-- ============================================================

CREATE TABLE commodity_prices (
    time        TIMESTAMPTZ NOT NULL,
    commodity   commodity_type NOT NULL,
    benchmark   TEXT NOT NULL,              -- e.g. 'BRENT', 'API2', 'LME_COPPER'
    price       DECIMAL(14,4) NOT NULL,
    currency    CHAR(3) NOT NULL DEFAULT 'USD',
    unit        TEXT NOT NULL,              -- 'barrel', 'tonne', 'mmbtu'
    source      TEXT NOT NULL,              -- 'eia', 'lme', 'quandl', 'manual'
    is_delayed  BOOLEAN NOT NULL DEFAULT TRUE  -- free sources have delay
);

SELECT create_hypertable('commodity_prices', 'time',
    chunk_time_interval => INTERVAL '1 month');

SELECT add_retention_policy('commodity_prices',
    INTERVAL '5 years');

ALTER TABLE commodity_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'commodity'
);
SELECT add_compression_policy('commodity_prices',
    INTERVAL '30 days');

CREATE UNIQUE INDEX idx_cp_unique ON commodity_prices(time, commodity, benchmark, source);
CREATE INDEX idx_cp_commodity_time ON commodity_prices(commodity, time DESC);

-- ============================================================
-- ALERT EVENTS  [TimescaleDB hypertable]
-- ============================================================

CREATE TABLE alert_events (
    id          UUID NOT NULL DEFAULT gen_random_uuid(),
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    type        alert_type NOT NULL,
    severity    alert_severity NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT,
    commodity   commodity_type,             -- NULL if not commodity-specific
    region      TEXT,                       -- affected region/country
    port_id     UUID REFERENCES ports(id),
    mmsi        BIGINT,                     -- if AIS-related
    source      TEXT,                       -- 'gdelt', 'ais_anomaly', 'price_engine'
    source_url  TEXT,
    metadata    JSONB,                      -- flexible extra data
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (id, time)
);

SELECT create_hypertable('alert_events', 'time',
    chunk_time_interval => INTERVAL '1 week');

SELECT add_retention_policy('alert_events',
    INTERVAL '1 year');

-- Compression: compress chunks older than 7 days
ALTER TABLE alert_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'type'
);
SELECT add_compression_policy('alert_events',
    INTERVAL '7 days');

CREATE INDEX idx_ae_type_time ON alert_events(type, time DESC);
CREATE INDEX idx_ae_severity ON alert_events(severity, time DESC) WHERE is_active = TRUE;
CREATE INDEX idx_ae_commodity ON alert_events(commodity, time DESC);

-- ============================================================
-- SIMULATIONS
-- ============================================================

CREATE TABLE simulations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    celery_task_id  TEXT,                   -- Celery task ID for polling
    title           TEXT NOT NULL,
    node            TEXT NOT NULL,          -- e.g. 'port_newcastle_au'
    event_type      TEXT NOT NULL,          -- e.g. 'flood', 'strike', 'blockade'
    description     TEXT,                   -- user's free-text scenario description
    parameters      JSONB NOT NULL,         -- {duration_weeks, intensity, agents, horizon_days}
    status          simulation_status NOT NULL DEFAULT 'queued',
    progress        INT NOT NULL DEFAULT 0, -- 0-100
    progress_log    TEXT[],                 -- array of log lines for SSE streaming
    result          JSONB,                  -- prediction output once complete
    error_message   TEXT,
    agents_count    INT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_simulations_user ON simulations(user_id, created_at DESC);
CREATE INDEX idx_simulations_status ON simulations(status) WHERE status IN ('queued', 'running');
CREATE INDEX idx_simulations_celery ON simulations(celery_task_id);

-- ============================================================
-- REPORTS
-- ============================================================

CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    simulation_id   UUID REFERENCES simulations(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    status          report_status NOT NULL DEFAULT 'generating',
    pdf_url         TEXT,                   -- S3/CDN URL once generated
    share_token     TEXT UNIQUE,            -- public share link token
    share_expires_at TIMESTAMPTZ,
    page_count      INT,
    file_size_bytes INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_user ON reports(user_id, created_at DESC);
CREATE INDEX idx_reports_share ON reports(share_token) WHERE share_token IS NOT NULL;

-- ============================================================
-- USER ALERT SUBSCRIPTIONS
-- (which alerts a user wants to receive)
-- ============================================================

CREATE TABLE user_alert_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    commodity       commodity_type,         -- NULL = all commodities
    alert_type      alert_type,             -- NULL = all types
    min_severity    alert_severity NOT NULL DEFAULT 'warning',
    notify_email    BOOLEAN NOT NULL DEFAULT TRUE,
    notify_webhook  BOOLEAN NOT NULL DEFAULT FALSE,
    webhook_url     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, commodity, alert_type)
);

CREATE INDEX idx_uas_user ON user_alert_subscriptions(user_id);

-- ============================================================
-- BOTTLENECK NODES
-- (pre-seeded catalogue of 40 critical supply chain nodes)
-- ============================================================

CREATE TABLE bottleneck_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,   -- e.g. 'port_newcastle_au'
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,          -- 'port', 'strait', 'pipeline', 'rail'
    country_code    TEXT NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    commodities     commodity_type[],
    annual_volume_mt DECIMAL(14,2),
    global_share_pct DECIMAL(5,2),          -- % of global supply passing through
    baseline_risk   INT NOT NULL DEFAULT 3, -- 1-10
    description     TEXT,
    wikipedia_url   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bn_commodity ON bottleneck_nodes USING GIN(commodities);

-- ============================================================
-- CHOKEPOINT STATUS
-- (real-time congestion index per chokepoint — updated from AIS)
-- ============================================================

CREATE TABLE chokepoint_status (
    time            TIMESTAMPTZ NOT NULL,
    node_id         UUID NOT NULL REFERENCES bottleneck_nodes(id),
    vessel_count    INT NOT NULL DEFAULT 0,
    avg_speed_knots DECIMAL(5,2),
    congestion_index DECIMAL(5,2),          -- 0-10 computed score
    risk_level      TEXT NOT NULL DEFAULT 'normal',  -- 'normal','elevated','high','critical'
    notes           TEXT
);

SELECT create_hypertable('chokepoint_status', 'time',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_cs_node_time ON chokepoint_status(node_id, time DESC);

-- ============================================================
-- AUDIT LOG
-- (track sensitive operations for security/compliance)
-- ============================================================

CREATE TABLE audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,              -- e.g. 'api_key.create', 'plan.upgrade'
    resource    TEXT,                       -- e.g. 'simulation:uuid'
    ip_address  INET,
    user_agent  TEXT,
    metadata    JSONB
);

CREATE INDEX idx_audit_user_time ON audit_log(user_id, time DESC);
CREATE INDEX idx_audit_action ON audit_log(action, time DESC);

-- ============================================================
-- UPDATED_AT TRIGGER
-- (auto-update updated_at on any UPDATE)
-- ============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables that have updated_at
CREATE TRIGGER set_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON ports
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON trade_flows
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON simulations
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON bottleneck_nodes
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- ============================================================
-- SEED DATA — BOTTLENECK NODES
-- ============================================================

INSERT INTO bottleneck_nodes (slug, name, type, country_code, latitude, longitude,
    commodities, annual_volume_mt, global_share_pct, baseline_risk, description) VALUES

-- Energy — oil & gas
('strait_hormuz',     'Strait of Hormuz',       'strait', 'IR',  26.57,  56.25, ARRAY['crude_oil','lng']::commodity_type[],  2000, 30.0, 8, 'World''s most important oil chokepoint. ~21M bbl/day.'),
('strait_malacca',    'Strait of Malacca',       'strait', 'MY',   1.25, 103.66, ARRAY['crude_oil','lng','coal']::commodity_type[], 3200, 25.0, 5, '80% of oil to Asia-Pacific passes here.'),
('suez_canal',        'Suez Canal',              'strait', 'EG',  30.42,  32.34, ARRAY['crude_oil','lng']::commodity_type[],  1200, 12.0, 6, '12% of global trade. Closed 2021 for 6 days.'),
('bab_el_mandeb',     'Bab-el-Mandeb Strait',    'strait', 'DJ',  12.58,  43.47, ARRAY['crude_oil','lng']::commodity_type[],   900,  9.0, 9, 'Active Houthi threat as of 2024–2026.'),
('panama_canal',      'Panama Canal',            'strait', 'PA',   9.08, -79.68, ARRAY['lng','crude_oil']::commodity_type[],    450,  5.0, 5, 'Drought restrictions impacted capacity 2023.'),
('strait_gibraltar',  'Strait of Gibraltar',     'strait', 'MA',  35.97,  -5.45, ARRAY['crude_oil']::commodity_type[],          600,  7.0, 3, 'Atlantic–Mediterranean gateway.'),
('bosphorus',         'Bosphorus Strait',        'strait', 'TR',  41.12,  29.08, ARRAY['crude_oil']::commodity_type[],          180,  2.0, 5, 'Turkey controls — geopolitical risk.'),
('cape_of_ghh',       'Cape of Good Hope',       'strait', 'ZA', -34.36,  18.47, ARRAY['crude_oil','lng']::commodity_type[],    200,  2.0, 2, 'Bypass route for Suez closure.'),
('sabine_pass',       'Sabine Pass LNG Terminal','port',   'US',  29.73, -93.87, ARRAY['lng']::commodity_type[],                 90, 20.0, 4, 'Largest US LNG export terminal.'),

-- Coal
('port_newcastle_au', 'Port Newcastle',          'port',   'AU', -32.92, 151.78, ARRAY['coal']::commodity_type[],              160, 38.0, 6, 'World''s largest coal export terminal. Hunter Valley rail dependency.'),
('hay_point_au',      'Hay Point',               'port',   'AU', -21.28, 149.30, ARRAY['coal']::commodity_type[],               50, 12.0, 5, 'Queensland coking coal. BHP/Mitsubishi JV.'),
('abbot_point_au',    'Abbot Point',             'port',   'AU', -19.87, 148.08, ARRAY['coal']::commodity_type[],               50,  8.0, 4, 'Queensland Bowen Basin coal.'),
('richbay_zaf',       'Richards Bay Coal Term.', 'port',   'ZA', -28.80,  32.08, ARRAY['coal']::commodity_type[],               77, 15.0, 4, 'Primary South African coal export hub.'),

-- Iron ore
('port_hedland_au',   'Port Hedland',            'port',   'AU', -20.32, 118.57, ARRAY['iron_ore']::commodity_type[],          580, 55.0, 5, 'World''s largest iron ore export port. Pilbara — BHP.'),
('dampier_au',        'Dampier Port',            'port',   'AU', -20.65, 116.72, ARRAY['iron_ore','lng']::commodity_type[],    180, 17.0, 4, 'Pilbara — Rio Tinto.'),
('port_walcott_au',   'Port Walcott',            'port',   'AU', -20.85, 117.16, ARRAY['iron_ore']::commodity_type[],           85,  8.0, 3, 'Pilbara — Hancock Prospecting.'),
('tubarao_bra',       'Tubarão Port',            'port',   'BR', -20.29, -40.25, ARRAY['iron_ore']::commodity_type[],          120, 11.0, 3, 'Vale''s main iron ore export terminal.'),

-- Copper
('antofagasta_chl',   'Antofagasta Port',        'port',   'CL', -23.63, -70.40, ARRAY['copper']::commodity_type[],             35, 27.0, 5, 'Atacama Desert — 27% of global copper supply.'),
('callao_per',        'Port of Callao',          'port',   'PE', -12.05, -77.15, ARRAY['copper']::commodity_type[],             25, 12.0, 4, 'Peru primary copper & zinc export hub.'),
('ilo_per',           'Ilo Port',                'port',   'PE', -17.64, -71.34, ARRAY['copper']::commodity_type[],             15,  7.0, 3, 'Southern Peru copper.'),
('norilsk_rus',       'Norilsk',                 'port',   'RU',  69.33,  88.20, ARRAY['nickel','palladium','copper']::commodity_type[], 2, 40.0, 7, '40% global palladium. High sanctions risk.'),

-- Grain
('odessa_ukr',        'Port of Odessa',          'port',   'UA',  46.49,  30.75, ARRAY['wheat','soybeans']::commodity_type[],   60, 28.0, 9, 'Black Sea corridor. Active conflict zone.'),
('novorossiysk_rus',  'Novorossiysk',            'port',   'RU',  44.72,  37.77, ARRAY['wheat']::commodity_type[],              50, 20.0, 7, 'Russia wheat export hub. Sanctions risk.'),
('new_orleans_usa',   'New Orleans / Mississippi','port',  'US',  29.95, -90.07, ARRAY['wheat','soybeans']::commodity_type[],  100, 35.0, 4, '60% of US grain exports.'),
('santos_bra',        'Port of Santos',          'port',   'BR', -23.96, -46.33, ARRAY['soybeans','wheat']::commodity_type[],  130, 25.0, 3, 'Largest Latin American port.');

-- ============================================================
-- SEED DATA — INITIAL ADMIN USER placeholder
-- (replace with actual user after first Clerk login)
-- ============================================================

-- NOTE: Do not insert real credentials here.
-- The first user to sign up via Clerk with plan='enterprise'
-- should be manually promoted via:
--   UPDATE users SET plan='enterprise' WHERE email='your@email.com';

-- ============================================================
-- VIEWS (for common queries)
-- ============================================================

-- Latest position per vessel (for live map)
CREATE MATERIALIZED VIEW latest_vessel_positions AS
    SELECT DISTINCT ON (mmsi)
        mmsi, imo, vessel_name, vessel_type,
        latitude, longitude, speed_knots, course,
        destination, flag_country, cargo_type, time
    FROM vessel_positions
    WHERE time > NOW() - INTERVAL '2 hours'
    ORDER BY mmsi, time DESC;

CREATE UNIQUE INDEX idx_lvp_mmsi ON latest_vessel_positions(mmsi);

-- Refresh this view every 5 minutes via pg_cron (set up separately)
-- SELECT cron.schedule('refresh-vessel-positions', '*/5 * * * *',
--     'REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vessel_positions');

-- Latest price per commodity (for dashboard)
CREATE VIEW latest_commodity_prices AS
    SELECT DISTINCT ON (commodity, benchmark)
        commodity, benchmark, price, currency, unit, time, source
    FROM commodity_prices
    ORDER BY commodity, benchmark, time DESC;

-- Active alerts (last 24h)
CREATE VIEW active_alerts AS
    SELECT * FROM alert_events
    WHERE time > NOW() - INTERVAL '24 hours'
      AND is_active = TRUE
    ORDER BY time DESC;
