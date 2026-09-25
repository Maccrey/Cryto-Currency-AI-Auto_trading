#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
UNIT_NAME="upbit-momentum-auto-trader.service"

mkdir -p "${UNIT_DIR}"
systemctl --user stop "${UNIT_NAME}" >/dev/null 2>&1 || true
install -m 0644 "${ROOT_DIR}/deploy/systemd/${UNIT_NAME}" "${UNIT_DIR}/${UNIT_NAME}"
systemctl --user daemon-reload
systemctl --user enable "${UNIT_NAME}"
echo "사용자 서비스 설치 완료: ${UNIT_NAME}"
echo "서버 시작: ${ROOT_DIR}/trade start"
