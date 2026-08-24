#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PLATFORM_BASE_URL:-http://127.0.0.1:8081}"
WORKSPACE_ID="${PLATFORM_WORKSPACE_ID:-demo}"
MESSAGE="${1:-Flow Matching 和 Diffusion 有什么区别？}"

conversation_json=$(curl -fsS -X POST "$BASE_URL/api/conversations" \
  -H 'Content-Type: application/json' \
  -d "{\"workspaceId\":\"$WORKSPACE_ID\"}")
conversation_id=$(printf '%s' "$conversation_json" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')

if [ -z "$conversation_id" ]; then
  echo "Could not parse conversation id: $conversation_json" >&2
  exit 1
fi

echo "Conversation: $conversation_id"
echo '--- SSE ---'
json_message=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}, ensure_ascii=False))' "$MESSAGE")
curl -fsS -N -X POST "$BASE_URL/api/conversations/$conversation_id/messages/stream" \
  -H 'Content-Type: application/json' \
  -d "$json_message"
printf '\n--- Persisted messages ---\n'
curl -fsS "$BASE_URL/api/conversations/$conversation_id/messages"
printf '\n'
