from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class LearningLogDiagnostics:
    """Summarize persisted learning logs for no-trade and AI-flow diagnosis."""

    def __init__(self, *, log_dir: Path) -> None:
        self._log_path = log_dir / "learning.jsonl"

    def build(self, *, tail_limit: int = 2000) -> dict[str, object]:
        events = self._read_tail(limit=tail_limit)
        event_counts = Counter(str(event.get("event_name")) for event in events)
        auto_cycles = [event for event in events if event.get("event_name") == "auto_trade_cycle"]
        fills = [event for event in events if event.get("event_name") == "fill_result"]
        signals = [event for event in events if event.get("event_name") == "signal_generated"]
        blocked_reasons = Counter(
            str((event.get("payload") or {}).get("reason"))
            for event in auto_cycles
            if (event.get("payload") or {}).get("reason") is not None
        )
        sizing_blocked_reasons = Counter(
            str((event.get("payload") or {}).get("sizing_blocked_reason"))
            for event in auto_cycles
            if (event.get("payload") or {}).get("sizing_blocked_reason") is not None
        )
        signal_reason_codes: Counter[str] = Counter()
        for event in signals:
            reason_codes = (event.get("payload") or {}).get("reason_codes") or []
            if isinstance(reason_codes, list):
                signal_reason_codes.update(str(code) for code in reason_codes)

        return {
            "status": "ok" if events else "empty",
            "log_path": str(self._log_path),
            "events_scanned": len(events),
            "event_counts": dict(event_counts),
            "last_event": None if not events else events[-1],
            "last_signal": None if not signals else signals[-1],
            "last_fill": None if not fills else fills[-1],
            "last_auto_cycle": None if not auto_cycles else auto_cycles[-1],
            "auto_cycle_status_counts": dict(
                Counter(str((event.get("payload") or {}).get("status")) for event in auto_cycles),
            ),
            "auto_cycle_blocked_reasons": dict(blocked_reasons),
            "sizing_blocked_reasons": dict(sizing_blocked_reasons),
            "signal_reason_codes": dict(signal_reason_codes),
            "diagnosis": self._diagnose(
                events=events,
                auto_cycles=auto_cycles,
                fills=fills,
                blocked_reasons=blocked_reasons,
                sizing_blocked_reasons=sizing_blocked_reasons,
            ),
        }

    def _read_tail(self, *, limit: int) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []
        lines = self._log_path.read_text(encoding="utf-8").splitlines()[-limit:]
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
        return events

    @staticmethod
    def _diagnose(
        *,
        events: list[dict[str, Any]],
        auto_cycles: list[dict[str, Any]],
        fills: list[dict[str, Any]],
        blocked_reasons: Counter[str],
        sizing_blocked_reasons: Counter[str],
    ) -> dict[str, object]:
        if not events:
            return {
                "state": "NO_LEARNING_LOG",
                "message": "학습 로그가 없어 AI 판단 흐름을 진단할 수 없습니다.",
            }
        if not auto_cycles:
            return {
                "state": "AUTO_TRADING_NOT_RUNNING",
                "message": "최근 로그에 auto_trade_cycle이 없어 서버 자동매매 루프가 실행되지 않았거나 새 코드 적용 전 로그입니다.",
            }
        if fills:
            return {
                "state": "TRADES_FOUND",
                "message": "최근 로그에서 체결 이벤트가 확인됩니다. 무거래라면 조회 기간 또는 서버 재시작 시점을 확인하세요.",
            }
        if blocked_reasons or sizing_blocked_reasons:
            return {
                "state": "TRADE_BLOCKED_BY_RULES",
                "message": "자동매매 루프는 실행됐지만 리스크/신호/사이징 규칙이 진입을 차단했습니다.",
            }
        return {
            "state": "WAITING_FOR_SIGNAL",
            "message": "자동매매 루프가 실행 중이지만 아직 체결 조건이 충족되지 않았습니다.",
        }
