#!/usr/bin/env bash
# Start the whole stack in dev mode: DB (docker compose) + backend + frontend.
# Backend and frontend run as background processes in this terminal,
# logs are written to _logs/. Press Ctrl+C to stop both.
#
# Usage:
#   bash scripts/dev-all.sh
#   bash scripts/dev-all.sh --no-browser

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

OPEN_BROWSER=1
for arg in "$@"; do
    case "$arg" in
        --no-browser) OPEN_BROWSER=0 ;;
        *) echo "[dev-all] unknown option: $arg"; exit 1 ;;
    esac
done

step() { echo "[dev-all] $*"; }

# ---------- 1) DB ----------
step "starting DB container..."
docker compose up -d

step "waiting for postgres healthy..."
for _ in $(seq 1 60); do
    status=$(docker inspect --format='{{.State.Health.Status}}' pg-interview 2>/dev/null || echo "")
    if [ "$status" = "healthy" ]; then
        step "postgres healthy"
        break
    fi
    sleep 0.5
done

# ---------- 2) Logs ----------
LOG_DIR="$PROJECT_ROOT/_logs"
mkdir -p "$LOG_DIR"

# ---------- 3) Backend ----------
step "starting backend (log: _logs/backend.log, port 8002)..."
bash "$PROJECT_ROOT/scripts/dev.sh" > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# ---------- 4) Frontend ----------
FRONTEND_DIR="$PROJECT_ROOT/frontend"
if [ ! -f "$FRONTEND_DIR/package.json" ]; then
    echo "[dev-all] frontend/package.json not found" >&2
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
fi

if [ ! -f "$FRONTEND_DIR/.env" ] && [ -f "$FRONTEND_DIR/.env.example" ]; then
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    step "frontend/.env created from .env.example"
fi

step "starting frontend (log: _logs/frontend.log, port 5173)..."
(
    cd "$FRONTEND_DIR"
    if [ ! -d node_modules ]; then
        npm install >> "$LOG_DIR/frontend.log" 2>&1
    fi
    npm run dev >> "$LOG_DIR/frontend.log" 2>&1
) &
FRONTEND_PID=$!

cleanup() {
    echo
    step "shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

# ---------- 5) Browser ----------
if [ "$OPEN_BROWSER" = "1" ]; then
    sleep 6
    if command -v open >/dev/null 2>&1; then
        open http://localhost:5173 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:5173 >/dev/null 2>&1 || true
    fi
fi

cat <<EOF

[dev-all] all started.
  - DB       : localhost:6543 (docker pg-interview)
  - Backend  : http://localhost:8002  (Swagger /docs)
  - Frontend : http://localhost:5173

logs:
  tail -f _logs/backend.log
  tail -f _logs/frontend.log

press Ctrl+C to stop backend/frontend.
stop DB with: docker compose down
EOF

wait
