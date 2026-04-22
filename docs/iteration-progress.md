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
- README notes had drifted away from the current runtime behavior and no longer described the latest iteration accurately.

## What Was Fixed

- Added parallel backend workspaces and APIs for live and simulation trading:
  - `/api/v1/live/...`
  - `/api/v1/simulation/...`
- Added a persisted `TradingAutomationProfile` model plus automation save/run flows for both live and simulation.
- Added an explicit operator approval queue for semi-automatic/manual-only automation, plus recommendation rejection tracking.
- Built a shared `TradingWorkspace` frontend used by both `Live Trading` and `Simulation`, keeping layout and controls nearly identical across both modes.
- Moved stop editing, position closes, manual overrides, and position inspection into action menus and modal dialogs.
- Extended order/manual-position flows to support structured inputs for side, order type, sizing mode, strategy, provider, and stop settings.
- Fixed RSS refresh behavior by using checkpoint overlap, force-refresh backfill, sane duplicate handling, and per-feed diagnostics.
- Added news diagnostics UI with fetched/added/duplicate/stale/failure counts, sample titles, and feed-level status rows.
- Added live broker sync visibility and a manual sync action to the live trading workspace.
- Preserved existing risk, audit, provider, broker, simulation, and MCP code paths rather than replacing them.

## What Was Added

- Dedicated `Live Trading` page using the shared trading workspace.
- Reworked `Simulation` page to mirror the live workflow.
- Shared trading workspace components:
  - `TradingWorkspace`
  - `PositionManagementTable`
  - compact dialogs for order review, stop management, partial close, and position details
- Automation controls for:
  - enable/disable
  - approval mode
  - strategy allow-list
  - provider allow-list
  - tradable action allow-list
  - confidence threshold and default notional
- Operator workflow helpers for:
  - recommendation queue review
  - load-approved-signal into the order review ticket
  - reject queued recommendation explicitly
  - live broker sync with last-sync status visibility
- News diagnostics controls for latest refresh and force refresh with selectable backfill windows.
- This iteration progress document for future repo context.

## Remaining TODOs

- Live execution remains guarded/scaffolded until a supported broker execution path is intentionally enabled and verified.
- Market data and news are practical local-first sources, not exchange-grade/commercial feeds.
- Tables are denser and cleaner now, but full server-side sorting/filter persistence is still a future improvement.
- Automatic trading is now usable for live/simulation workflows, but richer approval queues and explicit “rejected by rule X” timelines can still be expanded further.
