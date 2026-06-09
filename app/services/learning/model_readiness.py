from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.learning.jsonl import iter_jsonl_objects


@dataclass(frozen=True)
class ModelTrainingThresholds:
    min_total_events: int = 2_000
    min_signal_events: int = 400
    min_fill_events: int = 60
    min_exit_events: int = 20
    min_blocked_cycles: int = 80


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
        scoped_counts: Counter[str] = Counter()
        market_state_counts: Counter[str] = Counter()
        total_events = 0
        blocked_cycles = 0
        first_event_at = None
        latest_event_at = None
        last_trade_at = None
        last_auto_rule_update_at = None
        reset_at = None

        for row in self._iter_rows():
            event_name = str(row.get("event_name"))
            recorded_at = str(row.get("recorded_at")) if self._event_datetime(row) is not None else None
            if recorded_at is not None:
                first_event_at = first_event_at or recorded_at
                latest_event_at = recorded_at
            if event_name in {"fill_result", "position_opened", "position_closed", "position_exit_completed"}:
                last_trade_at = recorded_at or last_trade_at
            if event_name == "auto_rule_update":
                last_auto_rule_update_at = recorded_at or last_auto_rule_update_at
                payload = row.get("payload") or {}
                if isinstance(payload, dict) and bool(payload.get("reset_learning_completion")):
                    scoped_counts.clear()
                    market_state_counts.clear()
                    total_events = 0
                    blocked_cycles = 0
                    reset_at = recorded_at
                    continue

            total_events += 1
            scoped_counts.update([event_name])
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            if event_name == "auto_trade_cycle" and payload.get("status") == "blocked":
                blocked_cycles += 1
            market_state = payload.get("market_state")
            if market_state in {"bull", "bear", "box"}:
                market_state_counts.update([str(market_state)])

        metrics = {
            "total_events": total_events,
            "signal_events": scoped_counts.get("signal_generated", 0),
            "fill_events": scoped_counts.get("fill_result", 0),
            "exit_events": scoped_counts.get("position_exit_completed", 0),
            "blocked_cycles": blocked_cycles,
        }
        required = {
            "total_events": self._thresholds.min_total_events,
            "signal_events": self._thresholds.min_signal_events,
            "fill_events": self._thresholds.min_fill_events,
            "exit_events": self._thresholds.min_exit_events,
            "blocked_cycles": self._thresholds.min_blocked_cycles,
        }
        gaps = {
            key: max(required[key] - metrics.get(key, 0), 0)
            for key in required
            if metrics.get(key, 0) < required[key]
        }
        completion_rate = self.completion_rate(metrics=metrics, required=required)
        return {
            "status": "ready" if not gaps else "not_ready",
            "log_path": str(self._log_path),
            "metrics": metrics,
            "required": required,
            "gaps": gaps,
            "completion_rate": completion_rate,
            "completion_percent": int(completion_rate * 100),
            "completion_reset_at": reset_at,
            "completion_scope": "since_last_auto_rule_update" if reset_at is not None else "all_learning_logs",
            "first_event_at": first_event_at,
            "latest_event_at": latest_event_at,
            "last_trade_at": last_trade_at,
            "last_auto_rule_update_at": last_auto_rule_update_at,
            "recommended_next_step": self._recommended_next_step(gaps),
            "planned_ml_extra": "ml",
            "planned_packages": ["tensorflow", "scikit-learn", "pandas", "pyarrow"],
        }

    @staticmethod
    def completion_rate(*, metrics: dict[str, int], required: dict[str, int]) -> float:
        keys = ["total_events", "signal_events", "fill_events", "exit_events", "blocked_cycles"]
        ratios: list[float] = []
        for key in keys:
            required_value = int(required.get(key, 0))
            if required_value <= 0:
                ratios.append(1.0)
                continue
            ratios.append(min(float(metrics.get(key, 0)) / required_value, 1.0))
        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

    def _iter_rows(self):
        return iter_jsonl_objects(self._log_path)

    @staticmethod
    def _last_completion_reset_index(rows: list[dict[str, Any]]) -> int | None:
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if row.get("event_name") != "auto_rule_update":
                continue
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if bool(payload.get("reset_learning_completion")):
                return index
        return None

    @classmethod
    def _first_event_at(cls, rows: list[dict[str, Any]]) -> str | None:
        for row in rows:
            if cls._event_datetime(row) is not None:
                return str(row.get("recorded_at"))
        return None

    @classmethod
    def _latest_event_at(cls, rows: list[dict[str, Any]]) -> str | None:
        for row in reversed(rows):
            if cls._event_datetime(row) is not None:
                return str(row.get("recorded_at"))
        return None

    @classmethod
    def _last_event_at(cls, rows: list[dict[str, Any]], event_names: set[str]) -> str | None:
        for row in reversed(rows):
            if str(row.get("event_name")) not in event_names:
                continue
            if cls._event_datetime(row) is not None:
                return str(row.get("recorded_at"))
        return None

    @staticmethod
    def _event_datetime(row: dict[str, Any]) -> datetime | None:
        value = row.get("recorded_at")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _recommended_next_step(gaps: dict[str, int]) -> str:
        if not gaps:
            return "데이터 기준을 충족했다. 오프라인 학습 파이프라인과 백테스트 게이트를 구현할 수 있다."
        if "fill_events" in gaps or "exit_events" in gaps:
            return "체결과 청산 결과가 부족하다. demo 자동 운용을 더 오래 실행해 결과 라벨을 확보해야 한다."
        if "blocked_cycles" in gaps:
            return "차단 사례가 부족하다. 신호/리스크 차단 로그가 충분히 쌓일 때까지 운영 데이터를 더 수집해야 한다."
        return "학습 로그 총량과 신호 이벤트가 부족하다. 자동 운용을 지속해 feature 분포를 더 확보해야 한다."
