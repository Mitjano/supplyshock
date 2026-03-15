# SupplyShock

**Real-time global commodity supply chain monitoring and prediction platform.**

Track vessel movements, commodity prices, trade flows, and supply chain disruptions — all in one place. Run multi-agent simulations to predict how events ripple through global markets.

## Quick Start

```bash
git clone https://github.com/Mitjano/supplyshock.git
cd supplyshock
cp .env.example .env   # fill in: CLERK_*, AISSTREAM_API_KEY
docker compose up -d
```

Open [localhost:5173](http://localhost:5173) (frontend) and [localhost:8000/docs](http://localhost:8000/docs) (API).

## Features

- **Live Vessel Map** — Real-time AIS positions from aisstream.io, rendered on MapLibre GL JS with 30s refresh
- **Commodity Prices** — EIA + Quandl price feeds for crude oil, coal, iron ore, copper, LNG
- **Trade Flow Visualization** — GeoJSON flow lines from UN Comtrade data, colored by commodity
- **Supply Chain Alerts** — GDELT news monitoring + AIS anomaly detection at 25 bottleneck nodes
- **Multi-Agent Simulation** — OASIS fork with commodity-specific agents (traders, shippers, governments)
- **Stripe Billing** — Free / Pro ($99/mo) / Business ($499/mo) / Enterprise plans

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Vue 3 +    │────▶│  FastAPI     │────▶│  PostgreSQL  │
│  MapLibre   │     │  + Celery    │     │  TimescaleDB │
│  + Pinia    │     │  + Redis     │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
                          │
                    ┌─────┴─────┐
                    │  AIS WS   │  GDELT  │  EIA  │  Comtrade
                    └───────────┘
```

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Celery |
| Database | PostgreSQL 16 + TimescaleDB (hypertables) |
| Frontend | Vue 3, Vite, Pinia, MapLibre GL JS |
| Auth | Clerk (JWT) |
| Payments | Stripe |
| Simulation | OASIS (CAMEL-AI) fork |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET/POST | `/api/v1/auth/me`, `/sync` | Auth + user sync |
| GET | `/api/v1/vessels` | Live vessel positions (bbox filter) |
| GET | `/api/v1/vessels/{mmsi}` | Vessel detail |
| GET | `/api/v1/vessels/{mmsi}/trail` | Vessel trail history |
| GET | `/api/v1/ports` | Ports (bbox, major, commodity filters) |
| GET | `/api/v1/commodities/prices` | Latest commodity prices |
| GET | `/api/v1/commodities/flows` | Trade flows (GeoJSON) |
| GET | `/api/v1/alerts` | Alert list |
| GET | `/api/v1/alerts/stream` | SSE live alert feed |
| GET | `/api/v1/bottlenecks` | Bottleneck nodes |
| GET | `/api/v1/bottlenecks/{slug}/status` | Chokepoint status |

Full API spec: [`openapi.yaml`](openapi.yaml)

## Development

```bash
# Backend tests
docker compose exec backend pytest -v

# Seed data
docker compose exec backend python scripts/seed_ports.py
docker compose exec backend python scripts/seed_trade_flows.py

# Frontend dev
cd frontend && npm install && npm run dev
```

## License

MIT
