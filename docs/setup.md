# Setup

## Requirements

- Docker Desktop or Docker Engine with Compose

## Local startup

```bash
cp .env.example .env
docker compose up --build
```

The repository also includes a default `.env` for immediate local startup.

The backend applies the initial Alembic migration and seeds baseline local data on startup when `AUTO_SEED_DEMO=true`.

Default Compose starts one frontend on port `3000`. To run the legacy provider-specific frontend containers as well:

```bash
docker compose --profile multi-provider up --build
```

## Key pages after startup

- `http://localhost:3000/live` for the guarded live trading workspace
- `http://localhost:3000/simulation` for the mirrored simulation workspace
- `http://localhost:3000/positions/live` and `/positions/simulation` for position management
- `http://localhost:3000/news` for RSS diagnostics, latest refresh status, and force-refresh backfill controls
- `http://localhost:3000/analytics` for model tournament metrics and CSV export
- `http://localhost:8000/docs` for the FastAPI API documentation

The optional `multi-provider` profile also starts dedicated provider/model ports on `3001-3003` and `4000-4004`.

## Manual seed

```bash
./scripts/seed-demo.sh
```

## Shutdown

```bash
./scripts/dev-down.sh
```
