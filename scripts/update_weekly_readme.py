#!/usr/bin/env python3
"""Append the last completed week's closed-trade performance to README.md."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
START_MARKER = "<!-- weekly-trading-performance:start -->"
END_MARKER = "<!-- weekly-trading-performance:end -->"
TABLE_HEADER = "| 주간 기간 (KST) | 모드 | 시장 | 매수 | 매도 | 승률 | 실현 수익률* |"
TABLE_RULE = "|---|---:|---|---:|---:|---:|---:|"
KST_TZ = timezone(timedelta(hours=9))
KST = time(0, tzinfo=KST_TZ)


def _run_git(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return result.stdout.strip() if capture else ""


def _prepare_git_push() -> None:
    branch = _run_git("branch", "--show-current", capture=True)
    if branch != "main":
        raise RuntimeError(f"자동 주간 업데이트는 main 브랜치에서만 실행합니다 (현재: {branch or 'detached'}).")
    if _run_git("status", "--porcelain", capture=True):
        raise RuntimeError("작업 트리에 변경이 있어 README 자동 푸시를 보류했습니다. 먼저 변경을 커밋하거나 정리하세요.")
    _run_git("fetch", "origin", "main")
    ahead = int(_run_git("rev-list", "--count", "origin/main..HEAD", capture=True) or "0")
    if ahead:
        subjects = _run_git("log", "--format=%s", "origin/main..HEAD", capture=True).splitlines()
        changed_files = _run_git("diff", "--name-only", "origin/main...HEAD", capture=True).splitlines()
        if not subjects or any(not subject.startswith("주간 매매 수익률 기록 갱신 (") for subject in subjects):
            raise RuntimeError("origin/main에 없는 일반 로컬 커밋이 있어 자동 푸시를 보류했습니다.")
        if any(path != "README.md" for path in changed_files):
            raise RuntimeError("자동 주간 커밋 이외의 변경이 포함되어 푸시를 보류했습니다.")
        _run_git("push", "origin", "main")
        _run_git("fetch", "origin", "main")
    _run_git("merge", "--ff-only", "origin/main")


def _previous_completed_week(now: datetime) -> tuple[datetime, datetime]:
    local_now = now.astimezone(KST_TZ)
    current_monday = local_now.date() - timedelta(days=local_now.weekday())
    end_date = current_monday
    start_date = end_date - timedelta(days=7)
    return datetime.combine(start_date, KST), datetime.combine(end_date, KST)


def _load_ledger_and_settings():
    sys.path.insert(0, str(ROOT_DIR))
    from app.core.settings import load_settings
    from app.core.trading_profile import learning_log_dir_for_coin_profile
    from app.services.execution.ledger import ExecutionLedger

    settings = load_settings()
    profile_dir = learning_log_dir_for_coin_profile(
        settings.learning_log_dir,
        settings.trading_profile,
        settings.trade_coin,
    )
    if settings.trading_mode == "live":
        profile_dir = profile_dir / "live" / settings.live_exchange
    ledger_path = profile_dir / "runtime-state" / "execution-ledger.json"
    return settings, ledger_path, ExecutionLedger(storage_path=ledger_path).list_records()


def _build_week_row(start: datetime, end: datetime) -> tuple[str, str]:
    from app.services.reporting.daily_goal import calculate_period_realized_performance

    settings, ledger_path, records = _load_ledger_and_settings()
    performance = calculate_period_realized_performance(records, start=start, end=end)
    weekly_records = [
        record for record in records
        if record.recorded_at is not None
        and start <= _parse_timestamp(record.recorded_at) < end
        and record.fill.status == "filled"
    ]
    buy_count = sum(1 for row in weekly_records if row.fill.side == "buy")
    sell_count = int(performance["sell_count"])
    if sell_count:
        win_rate = f"{int(performance['win_count']) / sell_count * 100:.1f}%"
        closed_rate = performance["closed_return_rate"]
        rate_text = "자료 없음" if closed_rate is None else f"{float(closed_rate) * 100:+.3f}%"
    else:
        win_rate = "-"
        rate_text = "미집계 (청산 없음)"

    period = f"{start.date().isoformat()} ~ {(end.date() - timedelta(days=1)).isoformat()}"
    mode = "실거래" if settings.trading_mode == "live" else "데모"
    market = settings.trade_market.replace("|", "\\|")
    row = f"| {period} | {mode} | {market} | {buy_count} | {sell_count} | {win_rate} | {rate_text} |"
    source = "원장 있음" if ledger_path.is_file() else "원장 파일 없음"
    return row, source


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST_TZ)
    return parsed.astimezone(KST_TZ)


def _replace_week_row(readme: str, row: str) -> str:
    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("README.md에서 주간 성과 자동 갱신 표식을 찾지 못했습니다.")
    start_index = readme.index(START_MARKER) + len(START_MARKER)
    end_index = readme.index(END_MARKER, start_index)
    section = readme[start_index:end_index]
    existing_rows: dict[str, str] = {}
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "주간 기간" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and " ~ " in cells[0]:
            existing_rows[cells[0].split(" ~ ", 1)[0]] = line
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    period_key = cells[0].split(" ~ ", 1)[0]
    existing_rows[period_key] = row
    table = "\n".join([
        "",
        "",
        "## 주간 매매 성과 (자동 갱신)",
        "",
        "매주 월요일 09:00 KST에 직전 월~일의 체결 원장을 집계해 GitHub에 반영합니다.",
        "",
        TABLE_HEADER,
        TABLE_RULE,
        *[existing_rows[key] for key in sorted(existing_rows, reverse=True)],
        "",
        "\\* 실현 수익률은 해당 주간에 청산된 수량의 순손익(매수·매도 수수료 반영)을 그 수량의 매입 원가로 나눈 값입니다. 미청산 보유분은 제외하며, 청산 체결이 없으면 미집계로 표시합니다. 주문 내역과 원화 금액은 README에 기록하지 않습니다.",
        "",
    ])
    return readme[:start_index] + table + readme[end_index:]


def _update(push: bool) -> bool:
    if push:
        _prepare_git_push()
    now = datetime.now().astimezone()
    start, end = _previous_completed_week(now)
    row, source = _build_week_row(start, end)
    readme_path = ROOT_DIR / "README.md"
    old = readme_path.read_text(encoding="utf-8")
    new = _replace_week_row(old, row)
    print(f"주간 성과: {row}")
    print(f"체결 원장 상태: {source}")
    if new == old:
        print("README가 이미 최신입니다. 커밋하지 않습니다.")
        return False
    if not push:
        print("미리보기만 완료했습니다 (--dry-run).")
        return True
    readme_path.write_text(new, encoding="utf-8")

    _run_git("add", "README.md")
    start_day = start.date().isoformat()
    end_day = (end.date() - timedelta(days=1)).isoformat()
    _run_git(
        "-c", "user.name=Codex", "-c", "user.email=codex@local",
        "commit", "-m", f"주간 매매 수익률 기록 갱신 ({start_day}~{end_day})",
    )
    _run_git("push", "origin", "main")
    print("주간 성과를 README.md에 기록하고 origin/main에 푸시했습니다.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--push", action="store_true", help="README 변경을 한국어 커밋으로 만들고 origin/main에 푸시합니다.")
    parser.add_argument("--dry-run", action="store_true", help="README를 수정하지 않고 이번 주에 쓸 행만 출력합니다.")
    args = parser.parse_args()
    if args.push and args.dry_run:
        parser.error("--push와 --dry-run은 함께 사용할 수 없습니다.")
    try:
        _update(push=args.push)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"주간 README 갱신 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
