#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PSX_PORT:-8000}"
HOST="${PSX_HOST:-127.0.0.1}"
echo "Starting PSX Trading Intelligence Dashboard on http://${HOST}:${PORT} ..."
exec python3 -m uvicorn psx_app.main:app --host "${HOST}" --port "${PORT}"
