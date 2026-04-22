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

## Key pages after startup

- `http://localhost:3000/live` for the guarded live trading workspace
- `http://localhost:3000/simulation` for the mirrored simulation workspace
- `http://localhost:3000/positions` for cross-book position management
- `http://localhost:3000/news` for RSS diagnostics, latest refresh status, and force-refresh backfill controls
- `http://localhost:8000/docs` for the FastAPI API documentation

All other provider/model workspaces keep the same routes on their dedicated ports.

## Manual seed

```bash
./scripts/seed-demo.sh
```

## Shutdown

```bash
./scripts/dev-down.sh
```
