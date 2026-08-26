#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:5173}"
STAMP="$(date +%s)"
OWNER="v22owner${STAMP}"
VIEWER="v22viewer${STAMP}"
PASSWORD="V22Smoke-${STAMP}!"
OWNER_COOKIE="/tmp/eduagent-v22-owner-${STAMP}.cookie"
VIEWER_COOKIE="/tmp/eduagent-v22-viewer-${STAMP}.cookie"
trap 'rm -f "$OWNER_COOKIE" "$VIEWER_COOKIE"' EXIT

json_field() {
  local key="$1"
  sed -n "s/.*\"${key}\":\"\([^\"]*\)\".*/\1/p"
}

echo "[1/8] Register owner candidate..."
OWNER_JSON="$(curl -fsS -c "$OWNER_COOKIE" -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' -d "{\"username\":\"$OWNER\",\"password\":\"$PASSWORD\",\"displayName\":\"V2.2 Smoke Owner\"}")"
OWNER_TOKEN="$(printf '%s' "$OWNER_JSON" | json_field accessToken)"
test -n "$OWNER_TOKEN"

echo "[2/8] Create isolated workspace..."
WORKSPACE_JSON="$(curl -fsS -X POST "$BASE/api/workspaces" -H "Authorization: Bearer $OWNER_TOKEN" -H 'Content-Type: application/json' -d "{\"name\":\"V2.2 Smoke $STAMP\"}")"
WORKSPACE_ID="$(printf '%s' "$WORKSPACE_JSON" | json_field id)"
test -n "$WORKSPACE_ID"
echo "Workspace: $WORKSPACE_ID"

echo "[3/8] Create authenticated conversation..."
CONV_JSON="$(curl -fsS -X POST "$BASE/api/conversations" -H "Authorization: Bearer $OWNER_TOKEN" -H "X-Workspace-Id: $WORKSPACE_ID" -H 'Content-Type: application/json' -d "{\"workspaceId\":\"$WORKSPACE_ID\"}")"
printf '%s\n' "$CONV_JSON"

echo "[4/8] Register second user..."
VIEWER_JSON="$(curl -fsS -c "$VIEWER_COOKIE" -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' -d "{\"username\":\"$VIEWER\",\"password\":\"$PASSWORD\",\"displayName\":\"V2.2 Smoke Viewer\"}")"
VIEWER_TOKEN="$(printf '%s' "$VIEWER_JSON" | json_field accessToken)"
test -n "$VIEWER_TOKEN"

echo "[5/8] OWNER grants VIEWER..."
curl -fsS -X PUT "$BASE/api/workspaces/$WORKSPACE_ID/members" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$VIEWER\",\"role\":\"VIEWER\"}"; echo

echo "[6/8] VIEWER can read documents..."
curl -fsS "$BASE/api/documents?workspaceId=$WORKSPACE_ID" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" >/tmp/eduagent-v22-viewer-read.json
cat /tmp/eduagent-v22-viewer-read.json; echo

echo "[7/8] VIEWER must NOT write documents..."
STATUS="$(curl -sS -o /tmp/eduagent-v22-viewer-write.json -w '%{http_code}' -X POST "$BASE/api/documents/text" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H 'Content-Type: application/json' \
  -d "{\"workspace_id\":\"$WORKSPACE_ID\",\"document_id\":\"rbac-smoke\",\"source\":\"rbac.md\",\"text\":\"must not be written\",\"document_type\":\"lab_document\",\"metadata\":{}}")"
if [ "$STATUS" != "403" ]; then
  echo "Expected HTTP 403, got $STATUS"
  cat /tmp/eduagent-v22-viewer-write.json
  exit 1
fi

echo "[8/8] Rotate refresh token..."
REFRESH_JSON="$(curl -fsS -b "$OWNER_COOKIE" -c "$OWNER_COOKIE" -X POST "$BASE/api/auth/refresh")"
REFRESHED_TOKEN="$(printf '%s' "$REFRESH_JSON" | json_field accessToken)"
test -n "$REFRESHED_TOKEN"

echo "V2.2 identity/RBAC smoke passed."
