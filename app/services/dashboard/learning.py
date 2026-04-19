from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from app.services.learning.service import LearningEvent


@dataclass(frozen=True)
class DashboardLearning:
    total_events: int
    last_event_name: str | None
    last_recorded_at: str | None
    event_counts: dict[str, int]
    recent_events: list[dict[str, object]]


@dataclass(frozen=True)
class DashboardLearningHealth:
    total_events: int
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

        return DashboardLearningHealth(
            total_events=len(events),
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
