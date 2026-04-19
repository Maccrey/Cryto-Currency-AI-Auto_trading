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


class DashboardLearningService:
    """Build dashboard-friendly learning event payloads."""

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
