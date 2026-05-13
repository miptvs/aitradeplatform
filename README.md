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
- removed fake live balances: Live Trading now shows Trading212 disconnected/not-synced until a real broker cash sync succeeds
- added the configurable “Always keep X% in cash” reserve rule with available-to-trade cash shown in Live and Simulation
- added fractional order sizing by portfolio percentage, fixed currency amount, or explicit fractional quantity, with risk-aware resize details
- expanded signal/trading actions beyond buy/sell to include close/reduce long and simulated short/cover-short workflows
- added separate simulation accounts per provider/model so models can compete side by side
- added an isolated replay/backtest scaffold for fair same-window model comparison without mutating live-forward simulation ledgers
- added a model tournament metrics endpoint/table with CSV export for simulation and replay results
- added operational health output for news freshness, market-data freshness, broker sync, scheduler state, selected live model health, and automation blockers
- added short realism knobs for simulation: borrow fee, short margin requirement, margin-call forced-close scaffold, partial-fill ratio, and a simplified exchange-hours guard
- locked live automation to exactly one configured live model profile
- isolated live-only configuration in the Settings > Live Trading tab
- fixed the RSS refresh path so checkpoint overlap, backfill, duplicates, backup feeds, and per-feed diagnostics are visible
- preserved the existing provider, risk, audit, broker, and signal foundations instead of resetting the repo

See [iteration-progress.md](./docs/iteration-progress.md) for a concise analysis of what existed, what was missing, what was fixed, and what remains.

## What is included

- `Next.js` frontend with dashboard, positions, orders, signals, simulation, analytics, news, settings, and API docs link
- `FastAPI` backend with versioned REST routes, SSE stream, SQLAlchemy models, Alembic migration, Celery worker/beat, Redis, and Postgres
- Provider abstraction with separate simulation/live model profiles for local and remote vendors
- One default frontend on `3000`; optional provider-specific frontends can be started with the `multi-provider` Compose profile
- Ollama sidecar image that preloads the configured local model catalog on startup
- Remote paid-provider scaffolds for `ChatGPT / OpenAI`, `Claude / Anthropic`, `Gemini / Google`, and `DeepSeek API`
- Central risk engine that validates orders before any simulated or live workflow
- Cash reserve rule that blocks or resizes buy-like orders which would spend the configured cash reserve, returning max allowed order value and fractional quantity
- First-class simulation engine with separate accounts, cash, slippage, fees, latency, and audit history
- Fractional simulation fills with configurable decimal precision per simulation account
- Per-model simulation ledgers for comparing provider/model performance independently
- Replay/backtest scaffold that stores replay runs/results separately from normal simulation orders, trades, positions, and cash
- Model comparison metrics and CSV export across simulation accounts and replay runs
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

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Optional multi-provider frontend ports:

```bash
docker compose --profile multi-provider up --build
```

That additionally starts the provider-specific frontend containers on `3001-3003` and `4000-4004`.

Demo login credentials:

- Username: `admin`
- Password: `admin123`

## Common commands

```bash
./scripts/dev-up.sh
./scripts/dev-down.sh
./scripts/seed-demo.sh
docker compose exec -T backend pytest tests -q
docker compose build backend frontend
```

Local checks without Docker:

```bash
cd services/backend && python -m compileall app tests && pytest tests -q
cd apps/frontend && npm run typecheck && npm run build && npm run test:smoke
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
- Live balance comes only from Trading212 sync. If Trading212 is missing, disabled, or failing, the UI shows not connected instead of fake money.
- Trading212 sync also mirrors accessible live holdings and pies into the Live Trading workspace; these are local ledger mirrors, not fake execution.
- Live automation is locked to exactly one configured live model. Simulation can still use many model accounts independently.
- Live short execution is not exposed for Trading212 because the adapter does not confirm support. Shorting is simulation-only when enabled per simulation account.
- Cash reserve is enforced for buy-like actions and simulated shorts; close/reduce/cover actions are not blocked by cash reserve.
- Replay/backtest results are stored under replay tables and do not alter live balances or normal simulation accounts.
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

- News now refreshes from real RSS feeds with checkpoint overlap, backup feeds, and per-feed diagnostics, but it is still RSS-first rather than a commercial market-data/news feed stack
- Market data uses lightweight external refreshes suitable for a local-first MVP, not institutional-grade real-time feeds
- Local-model signal generation depends on Ollama health and model speed; when a model is too slow or unhealthy the app now reports that clearly instead of showing fake signals
- Trading212 account cash, holdings, and pies sync is implemented for live display when API permissions allow it. Trading212 execution is intentionally not implemented; account sync/manual mirroring is the intended extension path
- Trading212 ticker validation uses the authenticated instrument metadata API, so you must set `TRADING212_API_KEY` and `TRADING212_API_SECRET` in the backend env for non-seeded ticker verification
- Simulation shorts are simplified for MVP comparison. Borrow fee, margin requirement, margin-call forced-close scaffolding, and simplified exchange-session checks now exist, but locate availability and full order-book/partial-fill market microstructure remain simplified.
- Replay/backtest uses stored market snapshots and stored model signals in chronological order. It avoids using prices after each replay timestamp, but it is still a scaffold and only as complete as the stored historical data.
- Authentication is simple local JWT auth suitable for a local deployment, not a hardened multi-user SaaS auth layer

## CI

GitHub Actions runs backend compile/tests, frontend type/build, Playwright smoke tests, and Docker build validation. The smoke tests mock backend API responses for critical money-facing screens: Simulation model comparison/replay/trace, and Live Trading disconnected Trading212 state.
