# Architecture

## High level

The platform is split into a UI app, API service, asynchronous worker stack, and local infrastructure:

- `frontend`: dense operator dashboard, forms, charts, SSE client
- `backend`: API, persistence, provider routing, risk engine, simulation engine, analytics, and mounted MCP server/client integration
- `worker`: periodic jobs for market refresh, news refresh, signal generation, health checks, and snapshots
- `scheduler`: Celery Beat process that emits the configured periodic jobs
- `postgres`: system of record for orders, positions, trades, signals, analytics snapshots, and audit logs
- `redis`: Celery broker plus lightweight event bus for SSE notifications

## Separation of concerns

- Route handlers only orchestrate request/response work
- Services own business rules and side effects
- SQLAlchemy models define persistence contracts
- Pydantic schemas define typed API boundaries
- Provider and broker adapters isolate uncertain third-party behavior from core business logic
- MCP tools expose standardized read-only trading context so models and future agents can consume portfolio/news/risk data without bypassing backend controls

## Execution modes

- `simulation`: first-class virtual account with cash, fees, slippage, latency, and dedicated histories
- `live`: broker-backed path, disabled by default, always passes through the risk engine
- `manual`: operator-sourced actions or positions, still audited and mode-tagged
- `auto`: system-sourced signals or orders, never directly executed without validation

## Event flow

1. Worker refreshes real market data and RSS news, or runs a provider-backed signal job.
2. Signal service fetches normalized context through the mounted MCP server, combines it with technical votes, fresh market data, and recent news, then asks the active model profile to synthesize a signal.
3. Operator or automation requests an order.
4. Risk service validates the request and records reasons.
5. Simulation service executes simulated orders or broker service handles live-scaffold actions.
6. Portfolio and analytics services recompute snapshots and performance summaries.
7. Event service publishes updates through Redis to the SSE endpoint.

## MCP integration

- The backend mounts a real streamable-HTTP MCP server at `/mcp/`
- The backend also includes an MCP client that connects to `MCP_SERVER_URL`
- Current MCP tools:
  - `get_signal_context`
  - `get_architecture_snapshot`
- Current MCP resources:
  - `platform://architecture`

This keeps tool contracts standardized while preserving the backend as the only place where risk checks, secret handling, and broker boundaries are enforced.
