from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from app.services.learning.service import LearningEvent


@dataclass(frozen=True)
class DashboardLearning:
    total_events: int
    severity: str
    state_message: str
    last_event_name: str | None
    last_recorded_at: str | None
    event_counts: dict[str, int]
    recent_events: list[dict[str, object]]


@dataclass(frozen=True)
class DashboardLearningHealth:
    total_events: int
    severity: str
    state_message: str
    last_recorded_at: str | None
    category_counts: dict[str, int]
    last_event_by_category: dict[str, str | None]


class DashboardLearningService:
    """Build dashboard-friendly learning event payloads."""

    CATEGORY_BY_EVENT_PREFIX: tuple[tuple[str, str], ...] = (
        ("signal_", "signals"),
        ("fill_", "fills"),
        ("position_", "positions"),
        ("promotion_", "promotion"),
        ("restart_", "recovery"),
        ("recovery_", "recovery"),
    )

    def build(
        self,
        *,
        events: list[LearningEvent],
    ) -> DashboardLearning | None:
        if not events:
            return None

        counts = Counter(event.event_name for event in events)
        last_event = events[-1]
        return DashboardLearning(
            total_events=len(events),
            severity=self._derive_summary_severity(last_event.event_name),
            state_message=self._derive_summary_message(last_event.event_name),
            last_event_name=last_event.event_name,
            last_recorded_at=last_event.recorded_at,
            event_counts=dict(counts),
            recent_events=[asdict(event) for event in events],
        )

    @staticmethod
    def to_payload(learning: DashboardLearning) -> dict[str, object]:
        return asdict(learning)

    def build_health(
        self,
        *,
        events: list[LearningEvent],
    ) -> DashboardLearningHealth | None:
        if not events:
            return None

        category_counts: Counter[str] = Counter()
        last_event_by_category: dict[str, str | None] = {}
        for event in events:
            category = self._categorize_event(event.event_name)
            category_counts[category] += 1
            last_event_by_category[category] = event.recorded_at

        health_severity = (
            "critical"
            if category_counts.get("recovery", 0) > 0 and any(
                event.event_name == "hard_stop_triggered" for event in events
            )
            else "info"
        )
        health_message = (
            "최근 학습 이벤트에 하드스톱 관련 기록이 포함되어 있습니다."
            if health_severity == "critical"
            else "최근 학습 상태가 정상적으로 기록되고 있습니다."
        )

        return DashboardLearningHealth(
            total_events=len(events),
            severity=health_severity,
            state_message=health_message,
            last_recorded_at=events[-1].recorded_at,
            category_counts=dict(category_counts),
            last_event_by_category=last_event_by_category,
        )

    @staticmethod
    def to_health_payload(health: DashboardLearningHealth) -> dict[str, object]:
        return asdict(health)

    def _categorize_event(self, event_name: str) -> str:
        for prefix, category in self.CATEGORY_BY_EVENT_PREFIX:
            if event_name.startswith(prefix):
                return category
        return "other"

    @staticmethod
    def _derive_summary_severity(event_name: str) -> str:
        if event_name == "hard_stop_triggered":
            return "critical"
        if event_name.startswith("restart_"):
            return "warning"
        return "info"

    @staticmethod
    def _derive_summary_message(event_name: str) -> str:
        if event_name.startswith("signal_"):
            return "최근 학습 이벤트에 신호 생성이 기록되었습니다."
        if event_name.startswith("fill_"):
            return "최근 학습 이벤트에 체결 결과가 기록되었습니다."
        if event_name.startswith("position_"):
            return "최근 학습 이벤트에 포지션 변화가 기록되었습니다."
        if event_name.startswith("promotion_"):
            return "최근 학습 이벤트에 승격 검토가 기록되었습니다."
        if event_name == "hard_stop_triggered":
            return "최근 학습 이벤트에 하드스톱 상태가 기록되었습니다."
        if event_name.startswith("restart_") or event_name.startswith("recovery_"):
            return "최근 학습 이벤트에 복구 상태 변화가 기록되었습니다."
        return "최근 학습 이벤트가 기록되었습니다."
