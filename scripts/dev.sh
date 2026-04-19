#!/usr/bin/env bash
# Start both the FastAPI sidecar and Next.js dev server.
# Kills both on EXIT (Ctrl-C or shell exit).
#
# Prerequisites: export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
#   AWS_SESSION_TOKEN, AWS_REGION before running.
set -euo pipefail

cd "$(dirname "$0")/.."

# Install Python dependencies quietly if missing.
pip install -q -r requirements.txt

# Start API sidecar in background.
bash scripts/run_api.sh &
API_PID=$!

# Ensure both processes are killed on EXIT.
trap 'kill "$API_PID" 2>/dev/null; kill "$UI_PID" 2>/dev/null; wait' EXIT

# Start Next.js dev server.
(cd ui && npm run dev) &
UI_PID=$!

# Wait for either process to exit.
wait -n 2>/dev/null || wait
