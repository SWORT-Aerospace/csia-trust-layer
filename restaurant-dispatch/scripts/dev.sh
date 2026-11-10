#!/usr/bin/env bash
# Start Syncora locally: web server + timer worker.
# Usage: scripts/dev.sh [port]     (default port 8000)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
PY="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PY" ]; then
  echo "No virtualenv found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
"$PY" manage.py migrate --noinput
"$PY" manage.py seed_demo
"$PY" manage.py run_dispatch_worker &
WORKER=$!
trap 'kill $WORKER 2>/dev/null || true' EXIT INT TERM
echo
echo "  Homepage:   http://127.0.0.1:${PORT}/"
echo "  Staff demo: http://127.0.0.1:${PORT}/demo/"
echo "  Sign in:    http://127.0.0.1:${PORT}/signin/"
echo
"$PY" manage.py runserver "127.0.0.1:${PORT}"
