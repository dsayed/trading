#!/usr/bin/env bash
set -euo pipefail

# ── Trading System Launcher (macOS / Linux) ──
# Starts both the backend API server and frontend dev server.
# Press Ctrl+C to stop everything.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null
    wait 2>/dev/null
    echo "All servers stopped."
}

trap cleanup EXIT

# ── Check prerequisites ──
if ! command -v uv &>/dev/null; then
    echo "Error: 'uv' is not installed. See SETUP.md for installation instructions."
    exit 1
fi

if ! command -v npm &>/dev/null; then
    echo "Error: 'npm' is not installed. See SETUP.md for installation instructions."
    exit 1
fi

# ── Install dependencies if needed ──
if [ ! -d ".venv" ]; then
    echo "First run detected — installing Python dependencies..."
    uv sync --extra dev
fi

if [ ! -d "dashboard/node_modules" ]; then
    echo "First run detected — installing frontend dependencies..."
    (cd dashboard && npm install)
fi

# ── Start backend ──
echo "Starting backend server (port 9000)..."
uv run trading-server &
BACKEND_PID=$!

# Give the backend a moment to start
sleep 2

# ── Start frontend ──
echo "Starting frontend dev server (port 5173)..."
(cd dashboard && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo "  Backend:   http://localhost:9000"
echo "  Dashboard: http://localhost:5173"
echo "========================================="
echo "  Press Ctrl+C to stop all servers"
echo "========================================="
echo ""

# Wait for either process to exit
wait
