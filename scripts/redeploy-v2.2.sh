#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/6] Build V2.2 platform and frontend..."
docker compose build platform-server frontend

echo "[2/6] Recreate changed services..."
docker compose up -d --force-recreate api platform-server frontend

echo "[3/6] Wait for FastAPI..."
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/eduagent-v22-api-health.json 2>/dev/null; then
    cat /tmp/eduagent-v22-api-health.json; echo
    break
  fi
  sleep 2
  if [ "$i" -eq 40 ]; then docker compose logs api --tail=150; exit 1; fi
done

echo "[4/6] Wait for Spring Platform..."
for i in $(seq 1 50); do
  if curl -fsS http://127.0.0.1:${PLATFORM_SERVER_PORT:-8081}/actuator/health >/tmp/eduagent-v22-platform-health.json 2>/dev/null; then
    cat /tmp/eduagent-v22-platform-health.json; echo
    break
  fi
  sleep 2
  if [ "$i" -eq 50 ]; then docker compose logs platform-server --tail=200; exit 1; fi
done

echo "[5/6] Verify Flyway V2 migration..."
docker compose exec -T mysql mysql \
  -u"${PLATFORM_MYSQL_USER:-eduagent}" \
  -p"${PLATFORM_MYSQL_PASSWORD:-eduagent}" \
  "${PLATFORM_MYSQL_DATABASE:-eduagent_platform}" \
  -e "SHOW TABLES; SELECT installed_rank,version,description,success FROM flyway_schema_history ORDER BY installed_rank;"

echo "[6/6] Frontend..."
curl -fsSI http://127.0.0.1:5173 | head -n 1

echo "V2.2 is deployed. Run: ./scripts/smoke-v2.2.sh"
