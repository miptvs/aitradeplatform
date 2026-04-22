# Broker Integration

## Current adapters

- `paper`: safe scaffold for local/paper account workflows
- `trading212`: integration scaffold with explicit unsupported execution paths

## Trading212 notes

The MVP intentionally does not fake direct Trading212 execution. The adapter exposes clear connection and sync scaffolding plus TODO markers for:

- account sync
- positions sync
- order sync
- manual mirroring workflows
- authenticated ticker validation for manual-position search via `/api/v0/equity/metadata/instruments`

Ticker validation uses Trading212 only when backend credentials are configured through broker secrets or the `TRADING212_API_KEY` and `TRADING212_API_SECRET` env vars. If those credentials are missing, the UI falls back to local asset suggestions and clearly reports that external validation is unavailable.

If the integration details or permissions are unavailable, the platform remains fully usable through simulation mode.
