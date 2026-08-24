#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' '[1/5] Build platform-server Round 2...'
docker compose build platform-server

printf '%s\n' '[2/5] Recreate platform-server...'
docker compose up -d --force-recreate platform-server

printf '%s\n' '[3/5] Wait for platform health...'
for i in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8081/actuator/health >/tmp/eduagent-v21-health.json 2>/dev/null; then
    cat /tmp/eduagent-v21-health.json
    printf '\n'
    break
  fi
  if [ "$i" -eq 45 ]; then
    echo 'platform-server did not become healthy'
    docker compose logs platform-server --tail=200
    exit 1
  fi
  sleep 2
done

printf '%s\n' '[4/5] Verify FastAPI health from host...'
curl -fsS http://127.0.0.1:8000/health
printf '\n'

printf '%s\n' '[5/5] Ready for SSE smoke test.'
echo 'Run:'
echo '  ./scripts/smoke-v2.1-round2.sh'
