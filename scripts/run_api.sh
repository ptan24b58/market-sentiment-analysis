#!/usr/bin/env bash
# Start the FastAPI simulate sidecar on 127.0.0.1:8001.
# Supports API_PORT env var override: API_PORT=8002 ./scripts/run_api.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${API_PORT:-8001}"

# Check if the port is already in use and warn clearly.
if command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "ERROR: Port $PORT is already in use." >&2
        echo "Set API_PORT=<other_port> to use a different port, e.g.:" >&2
        echo "  API_PORT=8002 ./scripts/run_api.sh" >&2
        exit 1
    fi
fi

# Install dependencies quietly if missing.
pip install -q -r requirements.txt

exec python -m uvicorn src.api.simulate:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --reload \
    "$@"
