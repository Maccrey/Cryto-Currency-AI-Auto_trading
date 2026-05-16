#!/usr/bin/env zsh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

default_server_name() {
  local name
  name="$(scutil --get ComputerName 2>/dev/null || hostname 2>/dev/null || echo local-trading-server)"
  echo "${name%%.*}"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp_file
  tmp_file=".env.tmp.$$"
  if [[ -f .env ]] && grep -q "^${key}=" .env; then
    awk -F= -v key="${key}" -v value="${value}" 'BEGIN {OFS = "="} $1 == key {$0 = key "=" value} {print}' .env >"${tmp_file}"
    mv "${tmp_file}" .env
  else
    printf "%s=%s\n" "${key}" "${value}" >>.env
  fi
}

ensure_env_file() {
  if [[ ! -f .env && -f .env.example ]]; then
    cp .env.example .env
  fi
  if [[ ! -f .env ]]; then
    touch .env
  fi
  local configured_name
  configured_name="$(awk -F= '$1 == "SERVER_NAME" {print $2; exit}' .env)"
  if [[ -z "${configured_name}" || "${configured_name}" == "내-거래서버" ]]; then
    set_env_value SERVER_NAME "$(default_server_name)"
  fi
}

env_value() {
  local key="$1"
  if [[ -f .env ]]; then
    awk -F= -v key="${key}" '$1 == key {print $2; exit}' .env
  fi
}

python_version_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidate
  for candidate in python3.12 python3; do
    if command -v "${candidate}" >/dev/null 2>&1 && python_version_ok "${candidate}"; then
      command -v "${candidate}"
      return 0
    fi
  done
  return 1
}

install_homebrew() {
  if command -v brew >/dev/null 2>&1; then
    return 0
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 1
  fi
  echo "Homebrew가 없어 설치를 시도합니다..."
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

install_python() {
  echo "Python 3.12 이상이 없어 설치를 시도합니다..."
  if [[ "$(uname -s)" == "Darwin" ]]; then
    install_homebrew
    brew install python@3.12 || brew install python
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
    return 0
  fi
  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip
    return 0
  fi
  if command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3 python3-pip
    return 0
  fi
  echo "지원되는 Python 자동 설치 방법을 찾지 못했습니다. Python 3.12 이상을 설치한 뒤 다시 실행하세요." >&2
  return 1
}

ensure_python() {
  if PYTHON_BIN="$(find_python)"; then
    echo "Python 확인: ${PYTHON_BIN}"
    return 0
  fi
  install_python
  PYTHON_BIN="$(find_python)"
  echo "Python 설치 확인: ${PYTHON_BIN}"
}

ensure_venv() {
  if [[ ! -x .venv/bin/python ]]; then
    "${PYTHON_BIN}" -m venv .venv
  fi
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  if ! .venv/bin/python -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -e .
  fi
}

ensure_env_file

TRADING_HOST="${TRADING_HOST:-$(env_value DASHBOARD_HOST)}"
TRADING_HOST="${TRADING_HOST:-0.0.0.0}"
TRADING_PORT="${TRADING_PORT:-$(env_value DASHBOARD_PORT)}"
TRADING_PORT="${TRADING_PORT:-8080}"
STORAGE_DIR="${STORAGE_DIR:-$(env_value STORAGE_DIR)}"
STORAGE_DIR="${STORAGE_DIR:-${ROOT_DIR}/storage}"
LOCAL_URL="http://127.0.0.1:${TRADING_PORT}"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}' || echo 127.0.0.1)"
if [[ "${TRADING_HOST}" == "0.0.0.0" || "${TRADING_HOST}" == "::" ]]; then
  BROWSER_HOST="${LAN_IP}"
else
  BROWSER_HOST="${TRADING_HOST}"
fi
APP_URL="http://${BROWSER_HOST}:${TRADING_PORT}"
DASHBOARD_URL="${APP_URL}/dashboard"
SETTINGS_URL="${APP_URL}/settings"
PID_FILE="${STORAGE_DIR}/runtime/server.pid"
LOG_FILE="${STORAGE_DIR}/runtime/server.log"
ERR_LOG_FILE="${STORAGE_DIR}/runtime/server.err.log"
LAUNCH_AGENT_LABEL="com.crypto-auto-trading"
LAUNCH_AGENT_FILE="${HOME}/Library/LaunchAgents/${LAUNCH_AGENT_LABEL}.plist"

mkdir -p "${STORAGE_DIR}/runtime"

is_listening() {
  lsof -nP -iTCP:"${TRADING_PORT}" -sTCP:LISTEN >/dev/null 2>&1
}

open_settings() {
  if command -v open >/dev/null 2>&1; then
    open -a "Google Chrome" "${SETTINGS_URL}" >/dev/null 2>&1 || open "${SETTINGS_URL}" >/dev/null 2>&1 || true
  fi
}

install_launch_agent() {
  if ! command -v launchctl >/dev/null 2>&1; then
    return 1
  fi
  mkdir -p "${HOME}/Library/LaunchAgents"
  cat >"${LAUNCH_AGENT_FILE}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCH_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd "${ROOT_DIR}" &amp;&amp; env TRADING_MODE="${TRADING_MODE:-demo}" LEARNING_ENABLED="${LEARNING_ENABLED:-true}" STORAGE_DIR="${STORAGE_DIR}" TRADING_HOST="${TRADING_HOST}" TRADING_PORT="${TRADING_PORT}" .venv/bin/python -m uvicorn app.main:app --host "${TRADING_HOST}" --port "${TRADING_PORT}"</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_FILE}</string>
  <key>StandardErrorPath</key>
  <string>${ERR_LOG_FILE}</string>
</dict>
</plist>
PLIST
  launchctl bootout "gui/$(id -u)" "${LAUNCH_AGENT_FILE}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${LAUNCH_AGENT_FILE}"
  launchctl enable "gui/$(id -u)/${LAUNCH_AGENT_LABEL}" >/dev/null 2>&1 || true
}

if is_listening; then
  echo "트레이딩 서버가 이미 실행 중입니다: ${APP_URL}"
  open_settings
  echo "대시보드: ${DASHBOARD_URL}"
  echo "설정창: ${SETTINGS_URL}"
  exit 0
fi

ensure_python
ensure_venv

echo "트레이딩 서버를 백그라운드에서 시작합니다..."
if install_launch_agent; then
  echo "macOS launchd KeepAlive로 등록했습니다: ${LAUNCH_AGENT_LABEL}"
else
  nohup env TRADING_MODE="${TRADING_MODE:-demo}" LEARNING_ENABLED="${LEARNING_ENABLED:-true}" STORAGE_DIR="${STORAGE_DIR}" TRADING_HOST="${TRADING_HOST}" TRADING_PORT="${TRADING_PORT}" \
    .venv/bin/python -m uvicorn app.main:app --host "${TRADING_HOST}" --port "${TRADING_PORT}" >>"${LOG_FILE}" 2>&1 &
  SERVER_PID=$!
  echo "${SERVER_PID}" >"${PID_FILE}"
  disown "${SERVER_PID}" 2>/dev/null || true
fi

for _ in {1..30}; do
  if curl -fsS "${LOCAL_URL}/health" >/dev/null 2>&1; then
    echo "트레이딩 서버 시작 완료: ${APP_URL}"
    open_settings
    echo "대시보드: ${DASHBOARD_URL}"
    echo "설정창: ${SETTINGS_URL}"
    echo "로그: ${LOG_FILE}"
    exit 0
  fi
  sleep 1
done

echo "서버 시작 확인에 실패했습니다. 로그를 확인하세요: ${LOG_FILE}, ${ERR_LOG_FILE}" >&2
exit 1
