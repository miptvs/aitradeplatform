# API Overview

Versioned API base path: `/api/v1`

## Route groups

- `/auth`
- `/health`
- `/settings`
- `/providers`
- `/brokers`
- `/watchlists`
- `/assets`
- `/market-data`
- `/news`
- `/events`
- `/signals`
- `/strategies`
- `/risk-rules`
- `/positions`
- `/orders`
- `/trades`
- `/portfolio`
- `/analytics`
- `/simulation`
- `/audit`
- `/alerts`
- `/stream`

FastAPI also exposes interactive OpenAPI docs at `/docs`.

## Hardening endpoints

- `GET /simulation/replay-runs` and `POST /simulation/replay-runs` manage isolated replay/backtest scaffold runs.
- `GET /analytics/model-comparison` compares simulation accounts and replay results by model/provider.
- `GET /analytics/model-comparison.csv` exports the same model comparison table as CSV.
- `GET /health/status` includes freshness, broker sync, model health, scheduler, news diagnostics, and warnings.
- `POST /live/broker-sync` manually syncs Trading212 account data when a live broker account is configured.
