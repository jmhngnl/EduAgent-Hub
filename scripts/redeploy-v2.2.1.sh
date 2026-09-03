#!/usr/bin/env bash
set -euo pipefail

cd "${1:-$(pwd)}"

echo "[1/5] Validate compose..."
docker compose config >/tmp/eduagent-v221-compose.yml

echo "[2/5] Build FastAPI + Java Platform..."
docker compose build api platform-server

echo "[3/5] Recreate changed services..."
docker compose up -d --force-recreate api platform-server

echo "[4/5] Wait for health..."
for i in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/eduagent-v221-api.json 2>/dev/null \
     && curl -fsS http://127.0.0.1:8081/actuator/health >/tmp/eduagent-v221-platform.json 2>/dev/null; then
    cat /tmp/eduagent-v221-api.json; echo
    cat /tmp/eduagent-v221-platform.json; echo
    break
  fi
  if [ "$i" -eq 45 ]; then
    docker compose logs api platform-server --tail=160
    exit 1
  fi
  sleep 2
done

echo "[5/5] Flyway / startup evidence..."
docker compose logs platform-server --tail=100 | grep -E "Flyway|schema|Started PlatformServerApplication" || true
echo "V2.2.1 Memory & Context deployment finished."
