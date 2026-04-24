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
