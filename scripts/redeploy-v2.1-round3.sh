#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Build Python runtime and React frontend..."
docker compose build api worker frontend

echo "[2/5] Recreate changed services..."
docker compose up -d --force-recreate api worker frontend

echo "[3/5] Wait for FastAPI..."
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/eduagent-api-health.json 2>/dev/null; then
    cat /tmp/eduagent-api-health.json; echo
    break
  fi
  sleep 2
  if [ "$i" -eq 40 ]; then
    docker compose logs api --tail=160
    exit 1
  fi
done

echo "[4/5] Verify platform server..."
curl -fsS http://127.0.0.1:8081/actuator/health; echo

echo "[5/5] Verify product UI..."
curl -fsSI http://127.0.0.1:5173/ | head -n 1

echo
echo "Round 3 deployed: http://127.0.0.1:5173"
