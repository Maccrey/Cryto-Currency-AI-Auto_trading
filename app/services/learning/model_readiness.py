from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelTrainingThresholds:
    min_total_events: int = 10_000
    min_signal_events: int = 2_000
    min_fill_events: int = 300
    min_exit_events: int = 100
    min_blocked_cycles: int = 300


class ModelTrainingReadinessService:
    """Evaluate whether learning logs are mature enough for ML model training."""

    def __init__(
        self,
        *,
        log_dir: Path,
        thresholds: ModelTrainingThresholds | None = None,
    ) -> None:
        self._log_path = log_dir / "learning.jsonl"
        self._thresholds = thresholds or ModelTrainingThresholds()

    def build(self) -> dict[str, object]:
        rows = self._read_rows()
        counts = Counter(str(row.get("event_name")) for row in rows)
        auto_cycles = [row for row in rows if row.get("event_name") == "auto_trade_cycle"]
        blocked_cycles = [
            row
            for row in auto_cycles
            if (row.get("payload") or {}).get("status") == "blocked"
        ]
        metrics = {
            "total_events": len(rows),
            "signal_events": counts.get("signal_generated", 0),
            "fill_events": counts.get("fill_result", 0),
            "exit_events": counts.get("position_exit_completed", 0),
            "blocked_cycles": len(blocked_cycles),
        }
        required = {
            "total_events": self._thresholds.min_total_events,
            "signal_events": self._thresholds.min_signal_events,
            "fill_events": self._thresholds.min_fill_events,
            "exit_events": self._thresholds.min_exit_events,
            "blocked_cycles": self._thresholds.min_blocked_cycles,
        }
        gaps = {
            key: max(required[key] - value, 0)
            for key, value in metrics.items()
            if value < required[key]
        }
        return {
            "status": "ready" if not gaps else "not_ready",
            "log_path": str(self._log_path),
            "metrics": metrics,
            "required": required,
            "gaps": gaps,
            "recommended_next_step": self._recommended_next_step(gaps),
            "planned_ml_extra": "ml",
            "planned_packages": ["tensorflow", "scikit-learn", "pandas", "pyarrow"],
        }

    def _read_rows(self) -> list[dict[str, Any]]:
        if not self._log_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self._log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    @staticmethod
    def _recommended_next_step(gaps: dict[str, int]) -> str:
        if not gaps:
            return "데이터 기준을 충족했다. 오프라인 학습 파이프라인과 백테스트 게이트를 구현할 수 있다."
        if "fill_events" in gaps or "exit_events" in gaps:
            return "체결과 청산 결과가 부족하다. demo 자동 운용을 더 오래 실행해 결과 라벨을 확보해야 한다."
        if "blocked_cycles" in gaps:
            return "차단 사례가 부족하다. 신호/리스크 차단 로그가 충분히 쌓일 때까지 운영 데이터를 더 수집해야 한다."
        return "학습 로그 총량과 신호 이벤트가 부족하다. 자동 운용을 지속해 feature 분포를 더 확보해야 한다."
