#!/usr/bin/env bash
set -euo pipefail

docker compose run --rm quote-api python -m app.db.migrations
docker compose run --rm quote-api python -c "from app.db.session import verify_schema_version; verify_schema_version(); print('schema OK')"
docker compose up -d --build --remove-orphans
docker image prune -f

