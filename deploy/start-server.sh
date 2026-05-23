#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/maccrey/Crypo_Auto_Trading"
cd "${ROOT_DIR}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

export PYTHONUNBUFFERED=1
export TRADING_MODE="${TRADING_MODE:-demo}"
export LEARNING_ENABLED="${LEARNING_ENABLED:-true}"
export STORAGE_DIR="${STORAGE_DIR:-${ROOT_DIR}/storage}"

TRADING_HOST="${TRADING_HOST:-${DASHBOARD_HOST:-0.0.0.0}}"
TRADING_PORT="${TRADING_PORT:-${DASHBOARD_PORT:-8080}}"
LOG_DIR="${STORAGE_DIR}/runtime"

mkdir -p "${LOG_DIR}"

exec "${ROOT_DIR}/.venv/bin/python" -m uvicorn app.main:app \
  --host "${TRADING_HOST}" \
  --port "${TRADING_PORT}"
