#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
cd "${REPO_ROOT}"

COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"
FRONTEND_URL="http://127.0.0.1:8099"
BACKEND_HEALTH="http://127.0.0.1:8099/api/v1/healthz"
BACKEND_READY="http://127.0.0.1:8099/api/v1/readyz"
TIMEOUT="${START_TIMEOUT:-60}"
MODE="${1:-start}"

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "[error] Docker is not installed or not on PATH." >&2
    exit 127
  fi

  if ! docker compose version >/dev/null 2>&1; then
    echo "[error] 'docker compose' is not available. Install Docker Compose." >&2
    exit 127
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "[error] Docker daemon is not running. Start Docker and retry." >&2
    exit 69
  fi

  if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "[error] docker-compose.yml missing at ${COMPOSE_FILE}." >&2
    exit 66
  fi
}

poll() {
  local elapsed=0
  while [ "${elapsed}" -lt "${TIMEOUT}" ]; do
    if curl -fsS "${BACKEND_HEALTH}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
    echo "[..] Waiting for backend health (${elapsed}s of ${TIMEOUT}s)..."
  done
  return 1
}

case "${MODE}" in
  start|up)
    ensure_docker
    echo "[info] Building and starting services..."
    docker compose up -d --build
    echo "[info] Waiting for backend health/readiness..."
    if ! poll; then
      echo "[error] Backend did not become healthy within ${TIMEOUT}s." >&2
      docker compose logs --tail=50 backend >&2 || true
      exit 1
    fi
    if ! curl -fsS "${BACKEND_READY}" >/dev/null 2>&1; then
      echo "[warning] Backend healthz OK but readiness not ready yet."
    fi
    echo "[success] System is running"
    echo "  Frontend: ${FRONTEND_URL}"
    echo "  Backend API: ${FRONTEND_URL}/api/v1"
    echo "  Backend snapshot: ${FRONTEND_URL}/api/v1/snapshot"
    echo "  WebSocket: ws://127.0.0.1:8099/ws/v1/metrics"
    echo "  To stop: ./start.sh stop"
    ;;
  stop|down)
    ensure_docker
    docker compose down
    echo "[info] Services stopped."
    ;;
  restart)
    "${BASH_SOURCE[0]}" down
    "${BASH_SOURCE[0]}" start
    ;;
  logs)
    ensure_docker
    docker compose logs -f --tail=100 "${2:-}"
    ;;
  status)
    ensure_docker
    docker compose ps
    ;;
  clean)
    ensure_docker
    echo "WARNING: This will remove compose containers/images (volumes retained by default)."
    read -r -p "Type 'yes' to continue: " answer
    if [ "${answer}" != "yes" ]; then
      echo "[info] Cancelled."
      exit 0
    fi
    docker compose down --rmi local
    echo "[info] Cleaned."
    ;;
  build)
    ensure_docker
    docker compose build
    ;;
  test)
    (cd backend && uv run pytest -q) && (cd frontend && npm run test)
    ;;
  lint)
    (cd backend && uv run ruff check . && uv run mypy --strict src) && (cd frontend && npm run typecheck && npm run lint)
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|logs|status|build|clean|test|lint}" >&2
    exit 64
    ;;
esac
