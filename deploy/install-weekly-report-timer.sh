#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE_NAME="weekly-readme-report.service"
TIMER_NAME="weekly-readme-report.timer"

mkdir -p "${UNIT_DIR}"
cat >"${UNIT_DIR}/${SERVICE_NAME}" <<EOF
[Unit]
Description=Summarize the previous week's realized trading returns in README.md and push to GitHub
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${ROOT_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=GIT_TERMINAL_PROMPT=0
ExecStart=${ROOT_DIR}/.venv/bin/python ${ROOT_DIR}/scripts/update_weekly_readme.py --push
EOF
install -m 0644 "${ROOT_DIR}/deploy/systemd/${TIMER_NAME}" "${UNIT_DIR}/${TIMER_NAME}"
systemctl --user daemon-reload
systemctl --user enable --now "${TIMER_NAME}"
systemctl --user list-timers "${TIMER_NAME}" --no-pager
