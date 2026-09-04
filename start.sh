#!/usr/bin/env bash

set -e

APP_DIR="/opt/catalog_service"
DATA_DIR="/var/lib/catalog_service"

cd "$APP_DIR"

export PYTHONUNBUFFERED=1
export HF_HOME="$DATA_DIR/model-cache"
export CATALOG_DATABASE_URL="sqlite:////var/lib/catalog_service/catalog.db"

"$APP_DIR/.venv/bin/alembic" upgrade head

exec "$APP_DIR/.venv/bin/uvicorn" \
    app.main:app \
    --host 127.0.0.1 \
    --port 8000


