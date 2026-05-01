# Iteration Progress: Live/Simulation Usability Upgrade

## What Existed

- Strong backend foundation with FastAPI, SQLAlchemy, Redis, Postgres, Celery, audit logging, provider abstractions, risk services, and simulation services.
- Multi-workspace frontend with dashboard, settings, positions, orders, signals, news, analytics, and provider-specific ports.
- Signal generation, market-data refresh, broker scaffolds, and MCP plumbing already existed in the repo.
- Safety protections for live trading were already present and live execution remained backend-disabled by default.

## What Was Missing Or Fragile

- No dedicated `Live Trading` page with a complete manual plus automatic trading workflow.
- Simulation UX did not mirror live trading closely enough; the flows lived on separate, inconsistent screens.
- Position controls were too scattered and cluttered instead of being handled through compact menus and modals.
- News refresh diagnostics were too thin, and the RSS checkpoint logic could make refreshes appear to return zero useful articles.
- Signals were already shared conceptually, but the repo still lacked first-class traceability and lane-specific approval actions from a single canonical signal record.
- The signal trace feature existed, but orders, trades, and positions still felt like separate records because they did not expose the same provenance panel everywhere.
- Settings did not clearly explain when Simulation was intentionally mirroring Live automation versus using its own overrides.
- README notes had drifted away from the current runtime behavior and no longer described the latest iteration accurately.

## What Was Fixed

- Added parallel backend workspaces and APIs for live and simulation trading:
  - `/api/v1/live/...`
  - `/api/v1/simulation/...`
- Kept one canonical AI-generated signal pipeline and added explicit lane-specific approvals instead of duplicating signal generation per mode.
- Added signal detail and trace endpoints:
  - `/api/v1/signals/{signal_id}`
  - `/api/v1/signals/{signal_id}/trace`
- Extended decision-trail lookup so provenance can be opened from any primary trading object:
  - `/api/v1/orders/{order_id}/trace`
  - `/api/v1/trades/{trade_id}/trace`
  - `/api/v1/positions/{position_id}/trace`
- Added lane-specific signal approval endpoints:
  - `/api/v1/live/signals/{signal_id}/approve`
  - `/api/v1/simulation/signals/{signal_id}/approve`
- Added position action endpoints for compact stop/close/detail menus:
  - `/api/v1/live/positions/{position_id}/actions`
  - `/api/v1/simulation/positions/{position_id}/actions`
- Added a persisted `TradingAutomationProfile` model plus automation save/run flows for both live and simulation.
- Added scheduled automation profile controls plus a Celery Beat scanner that can run simulation automation on a configured interval.
- Added simulation automation inheritance so training can explicitly reuse the live automation policy when desired.
- Added an explicit operator approval queue for semi-automatic/manual-only automation, plus recommendation rejection tracking.
- Built a shared `TradingWorkspace` frontend used by both `Live Trading` and `Simulation`, keeping layout and controls nearly identical across both modes.
- Moved stop editing, position closes, manual overrides, and position inspection into action menus and modal dialogs.
- Extended order/manual-position flows to support structured inputs for side, order type, sizing mode, strategy, provider, and stop settings.
- Fixed RSS refresh behavior by using checkpoint overlap, force-refresh backfill, sane duplicate handling, and per-feed diagnostics.
- Added news diagnostics UI with fetched/added/duplicate/stale/failure counts, sample titles, and feed-level status rows.
- Added live broker sync visibility and a manual sync action to the live trading workspace.
- Added reverse trace resolution from orders, trades, and positions back to the root signal where available.
- Added manual-only provenance support so imported/manual positions still show lane, execution mode, stops, and audit trail even without a linked signal.
- Persisted richer trace response data for entrypoint, summary, risk checks, stop history, linked orders, linked trades, linked positions, and audit events.
- Preserved existing risk, audit, provider, broker, simulation, and MCP code paths rather than replacing them.

## What Was Added

- Dedicated `Live Trading` page using the shared trading workspace.
- Reworked `Simulation` page to mirror the live workflow.
- Shared signal trace dialog in both the global Signals page and the live/simulation workspaces.
- Shared provenance dialog and trace hook reused by Signals, Orders / Trades, Positions, Live Trading, and Simulation.
- Provenance chips for `LIVE`/`SIM`, `MANUAL`/`AUTO`, `SIGNAL-LINKED`/`MANUAL-ONLY`, and execution/risk status in trading tables.
- Shared trading workspace components:
  - `TradingWorkspace`
  - `PositionManagementTable`
  - compact dialogs for order review, stop management, partial close, and position details
- signal trace / rationale / linked-news / audit-chain inspection from one modal
- order/trade/position trace actions that show origin signal, provider/model, strategy, risk checks, stop history, downstream orders/trades/positions, and audit logs
- Automation controls for:
  - enable/disable
  - approval mode
  - strategy allow-list
  - provider allow-list
  - tradable action allow-list
  - confidence threshold and default notional
- shared-versus-overridden simulation automation controls, including `Use same settings as Live`
- Operator workflow helpers for:
  - recommendation queue review
  - load-approved-signal into the order review ticket
  - approve a shared signal directly into live review or simulation review
  - reject queued recommendation explicitly
  - live broker sync with last-sync status visibility
- News diagnostics controls for latest refresh and force refresh with selectable backfill windows.
- This iteration progress document for future repo context.

## Remaining TODOs

- Live execution remains guarded/scaffolded until a supported broker execution path is intentionally enabled and verified.
- Market data and news are practical local-first sources, not exchange-grade/commercial feeds.
- Tables are denser and cleaner now, but full server-side sorting/filter persistence is still a future improvement.
- Automatic trading is now usable for live/simulation workflows, but richer approval queues and explicit “rejected by rule X” timelines can still be expanded further.
- Stop history now records signal suggestions, ticket levels, current position levels, and manual edits where those events exist; future work can add a dedicated normalized stop-events table if stop automation becomes more complex.
- Provider settings are still intentionally split into simulation/live profiles; only automation policy inheritance is shared/overridable today.

## 2026-04-24 Trading Controls Upgrade

### Existing

- The repo already had shared live/simulation trading workspaces, automation profiles, Trading212 broker scaffolding, canonical signal records, risk validation, and simulation fills.
- Simulation orders already persisted provider/model on orders, but accounts were not model-specific and simulated trades did not carry provider/model identity.
- Trading212 credentials and manual sync UI existed, but live account summary could still fall back to seeded paper cash.

### Missing

- No configurable “always keep X% in cash” risk rule.
- Signal actions and automation were still biased toward `buy`/`sell`, with no first-class `close_long`, `reduce_long`, `short`, or `cover_short` action semantics.
- Simulation accounts were not isolated per provider/model, making model-vs-model comparison impossible.
- Live balance was not strictly sourced from Trading212.
- Live automation could still be configured with broad provider allow-lists instead of exactly one live model.

### Fixed In This Iteration

- Added a persisted `cash_reserve` risk rule and account summary fields for total cash, reserve amount, and available-to-trade cash.
- Risk validation now blocks buy-like actions that would breach the cash reserve and returns actionable reserve details.
- Expanded signal normalization and prompts to support `BUY`, `SELL`, `HOLD`, `CLOSE_LONG`, `REDUCE_LONG`, `SHORT`, and `COVER_SHORT`.
- Position exit scanning now emits `close_long` signals for held long positions instead of ambiguous sell-only signals.
- Simulation execution now supports short and cover-short flows when `short_enabled` is set on the selected simulation account.
- Added per-model simulation accounts keyed by provider profile/model, plus comparison metrics for cash, value, return, win rate, drawdown, and trade count.
- Trading212 sync now uses real account cash/info responses and persists synced cash, invested value, total value, realized/unrealized PnL, currency, and last sync metadata.
- Live workspace no longer displays fake paper cash; it shows Trading212 disconnected/not-synced states until a real sync succeeds.
- Live automation and live signal approval now require exactly one configured live provider/model and reject signals from the wrong live profile.
- Frontend settings now include a dedicated live-model selector and editable cash reserve rule.
- Live/Simulation workspaces now show cash reserve, available-to-trade cash, model comparison, short-simulation toggles, and expanded action controls.

### Remaining TODOs

- Trading212 execution remains intentionally unavailable until a fully verified live execution adapter is implemented.
- Trading212 live shorting is not exposed because the current adapter does not confirm short execution support.
- Provider health checks can be made stricter before live automation by requiring a fresh successful check within a configurable window.
- Simulation short accounting is intentionally simple for MVP comparison; margin, borrow cost, and locate rules are future work.

## 2026-04-29 Account Isolation And Broker Sync Fixes

### Existing

- Cash reserve validation existed, but automation could still create rejected buy orders when no available-to-trade cash remained.
- Per-model simulation accounts existed, but several risk checks still counted all simulation positions/orders together.
- Simulation reset cleared simulation-specific rows but not every generic order/trade/position row shown by the shared workspace.
- Trading212 account cash sync existed, while live holdings and pies were still scaffold-only.

### Fixed In This Iteration

- Automation now skips buy-like orders before submission when cash reserve leaves no available cash, so the rejection feed is not spammed by orders that were never processed.
- Fractional automation sizing now caps buy notional to available-to-trade cash and divides remaining budget across the run, supporting small live accounts around 100 EUR.
- Risk checks for duplicate orders, position count, sector exposure, daily loss, drawdown, and loss streak now scope to the selected simulation account or broker account.
- Simulation reset now clears the generic orders, trades, fills, positions, snapshots, simulation orders, and simulation trades for the selected model account only.
- Closed positions are shown separately below active positions and can be cleaned from the workspace without deleting audit/trade history.
- Position closing now handles fractional quantities, full-close defaults, short quantities, already-closed positions, and missing market data more gracefully.
- Trading212 sync now fetches account summary, positions, and pies when API permissions allow it; live positions are mirrored into the local live ledger as broker-synced holdings.
- Live account summary and broker status now show synced Trading212 holdings/pies counts and pie details, while direct execution remains disabled unless a future adapter verifies support.

### Remaining TODOs

- Trading212 order execution and live shorting remain intentionally unsupported.
- Trading212 pies are displayed as synced broker metadata; pie-level rebalancing/editing is not implemented.
- Broker-synced live positions are local mirrors. Closing them in the app updates the local ledger only unless a future verified execution adapter is added.

## 2026-04-30 Reliability Hardening Pass

### Existing State

- Cash reserve, expanded signal actions, per-model simulation accounts, Trading212 account sync, and live one-model locking were already partially implemented.
- The UI already had shared Live Trading and Simulation workspaces, model comparison cards, manual sync, signal trace dialogs, and RSS diagnostics.
- Tests existed for several backend risk, simulation, signal, and workspace flows.

### Changes Made In This Pass

- Added isolated replay/backtest persistence with `replay_runs` and `replay_model_results`.
- Added a replay service and Simulation API routes for creating/listing replay runs over a date range, starting cash, selected models, symbols, fees, slippage, cash reserve, and short settings.
- Added replay UI under Simulation with clear scaffold/limited-data labeling and model result tables.
- Added model tournament metrics and CSV export across simulation accounts and replay runs.
- Extended simulation comparison metrics with reserved cash, available cash, profit factor, rejected trades, invalid signal rate, and useful-signal rate.
- Added simulation realism settings for short borrow fee, short margin requirement, partial-fill ratio, and market-hours guard placeholder.
- Enforced short margin in the risk engine and applied short borrow fee to cover-short PnL.
- Enriched health status with news freshness, market-data freshness, broker sync, model health, scheduler status, latest signal time, and warnings.
- Added backend tests for replay isolation/results, Trading212 sync mapping/failure, reserve edge cases, live short rejection, healthy live model allowance, slippage, borrow fee, and margin blocking.
- Added Playwright smoke-test scaffolding for Simulation and Live Trading critical screens.
- Added GitHub Actions CI for backend tests, frontend type/build/smoke tests, and Docker build validation.
- Simplified Docker default runtime to one frontend; provider-specific frontends now require the `multi-provider` profile.
- Updated README plus replay/testing docs.

### Known Limitations

- Trading212 execution remains intentionally unavailable; the app syncs/mirrors account data but does not fake broker order placement.
- Replay/backtest is a scaffold using stored signals and stored historical snapshots. It avoids future price leakage for fills, but it does not yet regenerate each model over every historical timestep.
- Simulation short borrow fee and margin logic are simplified. Locate availability, forced margin calls, and full market-hours/partial-fill market microstructure are still future work.
- Frontend smoke tests mock backend responses; they verify page behavior and critical states, not a full browser-to-database integration run.

### Remaining TODOs

- Add real historical data ingestion jobs for deeper replay windows.
- Replace the deterministic market-hours scaffold with full exchange calendars if/when production-grade backtesting is required.
- Replace simplified margin-call liquidation with broker-specific maintenance-margin tiers before using it for live-like margin analysis.

## 2026-05-01 Remaining TODO Closeout

### Changes Made

- Added normalized `position_stop_events` persistence and included those events in signal/order/trade/position traces.
- Added a simplified exchange-hours service covering common US, London, and Xetra sessions, with holiday/unknown-exchange configuration hooks.
- Enforced simulation account market-hours settings in risk validation and direct simulation execution.
- Added optional replay market-hours enforcement through replay `config_json`.
- Added a simulated margin-call forced-close helper for short positions that breach configured margin requirements.
- Added provider usage parsing and model-cost estimation from configured per-token rates, plus model-cost aggregation in simulation/replay comparison metrics.
- Hardened RSS refresh after a live duplicate-URL failure: refresh now checks existing articles across the full database before insert, retries transient feed fetch failures with RSS-friendly headers, resolves stale RSS error alerts after a clean run, and lets the workspace clear system warning notices.
- Added tests for market-hours blocking/allowance, margin-call forced close, normalized stop provenance, and model-cost accounting.

### Known Limitations

- Trading212 execution and live shorting remain intentionally unavailable because the current adapter does not verify broker execution support.
- Market-hours logic is deterministic and lightweight; it is not a complete holiday/half-day exchange calendar.
- Margin-call forced close is simulation-only and simplified; real brokers may apply product-specific margin tiers and liquidation ordering.
