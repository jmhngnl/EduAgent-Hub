#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:5173}"
TMP_FILE="$(mktemp /tmp/eduagent-v21-smoke-XXXXXX.md)"
trap 'rm -f "$TMP_FILE"' EXIT

cat > "$TMP_FILE" <<'DOC'
# V2.1 smoke policy
EduAgent V2.1 document center smoke test. GPU reservation smoke keyword: V21-DOC-SMOKE-824.
DOC

echo "[1/5] Platform health"
curl -fsS "${BASE}/api/conversations?workspaceId=demo&limit=1" >/dev/null
echo "OK"

echo "[2/5] Existing document list"
curl -fsS "${BASE}/api/documents?workspaceId=demo" >/dev/null
echo "OK"

echo "[3/5] Upload through Browser -> Java BFF -> FastAPI"
UPLOAD_JSON="$(curl -fsS -X POST "${BASE}/api/documents/upload" \
  -F "workspaceId=demo" \
  -F "documentType=lab_document" \
  -F "documentId=v21-release-smoke" \
  -F "file=@${TMP_FILE};type=text/markdown")"
echo "$UPLOAD_JSON"
TASK_ID="$(printf '%s' "$UPLOAD_JSON" | sed -n 's/.*"task_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

if [ -n "$TASK_ID" ]; then
  echo "[4/5] Poll Celery task: $TASK_ID"
  for i in $(seq 1 40); do
    TASK_JSON="$(curl -fsS "${BASE}/api/document-tasks/${TASK_ID}")"
    echo "$TASK_JSON"
    if printf '%s' "$TASK_JSON" | grep -q '"state"[[:space:]]*:[[:space:]]*"SUCCESS"'; then
      break
    fi
    if printf '%s' "$TASK_JSON" | grep -q '"state"[[:space:]]*:[[:space:]]*"FAILURE"'; then
      echo "Celery ingestion failed" >&2
      exit 1
    fi
    sleep 2
  done
fi

echo "[5/5] Retrieval verification"
SEARCH_JSON="$(curl -fsS --get "${BASE}/api/knowledge/search" \
  --data-urlencode "workspaceId=demo" \
  --data-urlencode "documentType=lab_document" \
  --data-urlencode "query=V21-DOC-SMOKE-824" \
  --data-urlencode "topK=6")"
echo "$SEARCH_JSON"
printf '%s' "$SEARCH_JSON" | grep -q 'v21-release-smoke' || {
  echo "Smoke document was not returned by retrieval" >&2
  exit 1
}

echo "V2.1 release smoke passed."
