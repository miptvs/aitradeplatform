#!/usr/bin/env bash
set -euo pipefail

docker compose exec backend python -m app.db.seed
