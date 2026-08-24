#!/usr/bin/env bash
set -euo pipefail

wait_url() {
  local name="$1" url="$2"
  echo "Waiting for ${name}: ${url}"
  for i in $(seq 1 45); do
    if curl -fsS "$url" >/tmp/eduagent-v21-health 2>/dev/null; then
      cat /tmp/eduagent-v21-health
      echo
      return 0
    fi
    sleep 2
  done
  echo "${name} did not become ready" >&2
  return 1
}

echo "[1/5] Build V2.1 release services..."
docker compose build platform-server frontend

echo "[2/5] Recreate platform-server and frontend..."
docker compose up -d --force-recreate platform-server frontend

echo "[3/5] Wait for FastAPI runtime..."
wait_url "FastAPI" "http://127.0.0.1:8000/health"

echo "[4/5] Wait for Java platform..."
wait_url "Platform" "http://127.0.0.1:8081/actuator/health"

echo "[5/5] Verify frontend BFF..."
wait_url "Frontend" "http://127.0.0.1:5173/api/documents?workspaceId=demo"

echo "V2.1 release candidate is ready: http://127.0.0.1:5173"
