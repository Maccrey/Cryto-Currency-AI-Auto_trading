#!/usr/bin/env zsh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TRADING_HOST="${TRADING_HOST:-127.0.0.1}"
TRADING_PORT="${TRADING_PORT:-8000}"
APP_URL="http://${TRADING_HOST}:${TRADING_PORT}"
SETTINGS_URL="${APP_URL}/settings"
PID_FILE="${ROOT_DIR}/logs/runtime/server.pid"
LOG_FILE="${ROOT_DIR}/logs/runtime/server.log"
ERR_LOG_FILE="${ROOT_DIR}/logs/runtime/server.err.log"
LAUNCH_AGENT_LABEL="com.crypto-auto-trading"
LAUNCH_AGENT_FILE="${HOME}/Library/LaunchAgents/${LAUNCH_AGENT_LABEL}.plist"

mkdir -p "${ROOT_DIR}/logs/runtime"

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
    <string>cd "${ROOT_DIR}" &amp;&amp; env TRADING_MODE="${TRADING_MODE:-demo}" LEARNING_ENABLED="${LEARNING_ENABLED:-true}" uvicorn app.main:app --host "${TRADING_HOST}" --port "${TRADING_PORT}"</string>
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
  echo "설정창: ${SETTINGS_URL}"
  exit 0
fi

echo "트레이딩 서버를 백그라운드에서 시작합니다..."
if install_launch_agent; then
  echo "macOS launchd KeepAlive로 등록했습니다: ${LAUNCH_AGENT_LABEL}"
else
  nohup env TRADING_MODE="${TRADING_MODE:-demo}" LEARNING_ENABLED="${LEARNING_ENABLED:-true}" \
    uvicorn app.main:app --host "${TRADING_HOST}" --port "${TRADING_PORT}" >>"${LOG_FILE}" 2>&1 &
  SERVER_PID=$!
  echo "${SERVER_PID}" >"${PID_FILE}"
  disown "${SERVER_PID}" 2>/dev/null || true
fi

for _ in {1..30}; do
  if curl -fsS "${APP_URL}/health" >/dev/null 2>&1; then
    echo "트레이딩 서버 시작 완료: ${APP_URL}"
    open_settings
    echo "설정창: ${SETTINGS_URL}"
    echo "로그: ${LOG_FILE}"
    exit 0
  fi
  sleep 1
done

echo "서버 시작 확인에 실패했습니다. 로그를 확인하세요: ${LOG_FILE}, ${ERR_LOG_FILE}" >&2
exit 1
