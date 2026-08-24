#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not in PATH" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 is required" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review provider credentials before disabling MOCK_LLM."
fi

echo "[1/4] Building V2.1 services..."
docker compose build --pull api worker frontend platform-server

echo "[2/4] Starting services without deleting volumes..."
docker compose up -d --remove-orphans

echo "[3/4] Current service state:"
docker compose ps

echo "[4/4] Smoke checks:"
if command -v curl >/dev/null 2>&1; then
  PLATFORM_PORT="$(docker compose port platform-server 8080 | awk -F: '{print $NF}')"
  curl --fail --silent --show-error "http://127.0.0.1:${PLATFORM_PORT}/actuator/health" && echo
  curl --fail --silent --show-error "http://127.0.0.1:8000/health" && echo
  echo "Frontend: http://127.0.0.1:5173"
  echo "Platform API: http://127.0.0.1:${PLATFORM_PORT}/api/conversations"
else
  echo "curl not found; skip HTTP smoke checks."
fi
