# Testing Strategy

## Backend

Critical money-path tests live under `services/backend/tests` and cover:

- signal action normalization, bearish signals, and sell/short persistence
- risk checks for cash reserve, live short rejection, short margin, simplified market hours, stops, drawdown, and daily loss
- long, short, cover-short, slippage, borrow-fee simulation accounting, and margin-call forced closes
- per-model simulation account isolation and per-model reset behavior
- Trading212 sync mapping and sync-failure diagnostics
- live model enforcement and blocked live automation attempts
- replay/backtest isolation, persisted model results, and model-cost aggregation
- provenance traces from signal, order, trade, and position entrypoints, including normalized stop events

Run locally:

```bash
cd services/backend
python -m compileall app tests
pytest tests -q
```

## Frontend

Playwright smoke tests live under `apps/frontend/tests`. They mock the backend API and verify:

- Simulation page loads
- model/account comparison renders
- replay/backtest scaffold renders
- sell/short signals render
- signal trace dialog opens
- Live Trading shows disconnected Trading212 state instead of fake money
- live model selection/automation blocker messaging is visible

Run locally:

```bash
cd apps/frontend
npm run typecheck
npm run build
npm run test:smoke
```

## CI

`.github/workflows/ci.yml` runs backend compile/tests, frontend type/build, Playwright smoke tests, and Docker build validation for `backend` and the default `frontend`.
