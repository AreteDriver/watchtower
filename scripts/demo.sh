#!/usr/bin/env bash
# Launch Witness demo — seed data + API + frontend
# Usage: ./scripts/demo.sh
set -e

cd "$(dirname "$0")/.."

echo "=== Witness Demo Launcher ==="
echo ""

# 1. Seed demo database
echo "[1/3] Seeding demo database..."
WITNESS_DB_PATH=data/demo.db python -m scripts.seed_demo_runner
echo ""

# 2. Build frontend if needed
if [ ! -d frontend/dist ]; then
    echo "[2/3] Building frontend..."
    cd frontend
    npm install --silent
    npx vite build
    cd ..
else
    echo "[2/3] Frontend already built (frontend/dist exists)"
fi
echo ""

# 3. Start API server with demo DB
echo "[3/3] Starting API server on http://localhost:8000"
echo "  Dashboard: http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
echo ""
WITNESS_DB_PATH=data/demo.db python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
