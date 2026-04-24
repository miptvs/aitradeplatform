AI-assisted trading and portfolio analysis platform built as a Dockerized monorepo. The MVP emphasizes strict separation between simulation and live trading, pluggable model providers, auditability, typed APIs, and a dense trading-terminal style dashboard.

## Current iteration snapshot

This iteration upgrades the original MVP in place rather than replacing it:

- keeps one canonical AI-generated signal pool that feeds both Live Trading and Simulation
- adds shared decision-trail views so you can open a signal, order, trade, or position and follow origin, review, risk, order, trade, position, stops, and audit records
- adds simulation/live automation parity controls, including “use same settings as Live” for simulation policy inheritance
- adds scheduled simulation automation controls so eligible signals can be checked on a timer and converted into simulated orders only after risk validation
- added a dedicated `Live Trading` workspace with guarded manual and automation flows
- rebuilt `Simulation` to mirror the live trading workflow with the same shared workspace components
- moved position actions into compact dropdowns/modals for stop edits, partial closes, and manual overrides
- added provenance chips and `View trace` actions to orders, trades, positions, and the shared Live/Simulation trading workspace
- added an operator approval queue for semi-automatic/manual-only automation, with review-ticket loading and explicit rejection
- added live broker sync visibility plus a manual sync action in the live workspace
- fixed the RSS refresh path so checkpoint overlap, backfill, duplicates, and per-feed diagnostics are visible
- preserved the existing provider, risk, audit, broker, and signal foundations instead of resetting the repo

See [iteration-progress.md](./docs/iteration-progress.md) for a concise analysis of what existed, what was missing, what was fixed, and what remains.

## What is included

- `Next.js` frontend with dashboard, positions, orders, signals, simulation, analytics, news, settings, and API docs link
- `FastAPI` backend with versioned REST routes, SSE stream, SQLAlchemy models, Alembic migration, Celery worker/beat, Redis, and Postgres
- Provider abstraction with separate simulation/live model profiles for local and remote vendors
- Dedicated provider entry URLs on `3000-3003` for remote vendors and `4000-4004` for local-model families
- Ollama sidecar image that preloads the configured local model catalog on startup
- Remote paid-provider scaffolds for `ChatGPT / OpenAI`, `Claude / Anthropic`, `Gemini / Google`, and `DeepSeek API`
- Central risk engine that validates orders before any simulated or live workflow
- First-class simulation engine with separate accounts, cash, slippage, fees, latency, and audit history
- Broker adapter layer with `paper` and `Trading212` scaffold implementations
- Real MCP server mounted at `/mcp/` plus backend MCP client integration for standardized tool-based trading context
- Trading212-backed ticker validation for manual position search when backend API credentials are configured
- Seeded assets, rules, providers, and watchlists without preloaded fake live/simulation holdings

## Quickstart

1. Review envs if you want to change defaults:

```bash
cp .env.example .env
```

A ready-to-run `.env` is already included for local MVP startup, so you can also skip the copy step and edit it later if you prefer.

2. Start the stack:

```bash
docker compose up --build
```

3. Open the apps:

- Remote provider workspaces:
  - [http://localhost:3000](http://localhost:3000) for `ChatGPT / OpenAI`
  - [http://localhost:3001](http://localhost:3001) for `Claude / Anthropic`
  - [http://localhost:3002](http://localhost:3002) for `Gemini / Google`
  - [http://localhost:3003](http://localhost:3003) for `DeepSeek API`
- Local model workspaces:
  - [http://localhost:4000](http://localhost:4000) for `GPT OSS`
  - [http://localhost:4001](http://localhost:4001) for `Qwen 2.5`
  - [http://localhost:4002](http://localhost:4002) for `Qwen 3`
  - [http://localhost:4003](http://localhost:4003) for `Llama 3.1 / 3.2`
  - [http://localhost:4004](http://localhost:4004) for `DeepSeek-R1`
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Demo login credentials:

- Username: `admin`
- Password: `admin123`

## Common commands

```bash
./scripts/dev-up.sh
./scripts/dev-down.sh
./scripts/seed-demo.sh
docker compose exec -T backend pytest tests -q
```

## Architecture

- `apps/frontend`: Next.js 15 app-router dashboard
- `services/backend`: FastAPI service, business logic, Celery tasks, and persistence
- `docs`: setup, architecture, risk rules, provider routing, and broker scaffold notes
- `scripts`: local helper commands

See [architecture.md](./docs/architecture.md) and [setup.md](./docs/setup.md) for more detail.

## MCP endpoint

- Mounted MCP server: [http://localhost:8000/mcp/](http://localhost:8000/mcp/)
- MCP status via REST: [http://localhost:8000/api/v1/mcp/status](http://localhost:8000/api/v1/mcp/status)

The backend uses the official MCP Python SDK on both sides:
- mounted server tools/resources expose normalized portfolio/news/risk context
- internal MCP client calls those tools before model-backed signal generation

## MVP guarantees

- Live trading is disabled by default and controlled only from the backend
- Simulation and live flows use separate records and validation paths
- Signals are generated once, stored canonically, and can then be reviewed into either simulation or live workflows
- Market data and signals refresh every 5 minutes by default, news refreshes every 10 minutes, and scheduled simulation automation scans every minute to run only when the configured interval is due
- Orders, trades, and positions can resolve back into the same provenance chain, including manual-only records that have no origin signal
- Model settings are separated into simulation and actual-trading profiles for both local and remote providers
- Local model families each get their own simulation and actual-trading profile pair
- API keys are write-only from the frontend and stored encrypted server-side
- All critical changes and order attempts are written to the audit log
- Broker execution scaffolds never fake unsupported capabilities

## Local model preload

- The `ollama` container now starts automatically and attempts to preload:
  - `gpt-oss:20b`
  - `qwen2.5:7b-instruct`
  - `qwen3:8b`
  - `llama3.1:8b`
  - `llama3.2:3b`
  - `deepseek-r1:8b`
- This happens on container startup and stores models in the persistent `ollama_data` volume.
- First boot can take significant time and disk space because the models are downloaded locally.
- If you want the stack up immediately and prefer to pull later, set `OLLAMA_PRELOAD_MODELS=false` in `.env`.

## Known limits

- News now refreshes from real RSS feeds with checkpoint overlap and per-feed diagnostics, but it is still RSS-first rather than a commercial market-data/news feed stack
- Market data uses lightweight external refreshes suitable for a local-first MVP, not institutional-grade real-time feeds
- Local-model signal generation depends on Ollama health and model speed; when a model is too slow or unhealthy the app now reports that clearly instead of showing fake signals
- Trading212 execution is intentionally not implemented; account sync/manual mirroring is the intended extension path
- Trading212 ticker validation uses the authenticated instrument metadata API, so you must set `TRADING212_API_KEY` and `TRADING212_API_SECRET` in the backend env for non-seeded ticker verification
- Authentication is simple local JWT auth suitable for a local deployment, not a hardened multi-user SaaS auth layer
