from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LearningEvent:
    event_name: str
    market: str
    mode: str
    payload: dict[str, Any]
    recorded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class JsonlLearningExporter:
    """Append learning events to a single JSONL file."""

    def __init__(self, *, log_dir: Path) -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "learning.jsonl"

    def export(self, event: LearningEvent) -> None:
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True))
            handle.write("\n")


class LearningEventStore:
    """Keep recent learning events in memory for runtime inspection."""

    def __init__(self, *, history_limit: int = 200) -> None:
        self._events: deque[LearningEvent] = deque(maxlen=history_limit)

    def record(self, event: LearningEvent) -> None:
        self._events.append(event)

    def list_events(self, *, limit: int | None = None) -> list[LearningEvent]:
        events = list(self._events)
        if limit is None or limit >= len(events):
            return events
        return events[-limit:]

    @staticmethod
    def to_payload(event: LearningEvent) -> dict[str, Any]:
        return asdict(event)


class LearningService:
    """Record normalized learning events for every execution mode."""

    def __init__(
        self,
        *,
        log_dir: Path,
        event_store: LearningEventStore | None = None,
    ) -> None:
        self._exporter = JsonlLearningExporter(log_dir=log_dir)
        self._event_store = event_store or LearningEventStore()

    def record(self, event: LearningEvent) -> None:
        self._exporter.export(event)
        self._event_store.record(event)

    def record_many(self, events: list[LearningEvent]) -> None:
        for event in events:
            self.record(event)

    def recent_events(self, *, limit: int | None = None) -> list[LearningEvent]:
        return self._event_store.list_events(limit=limit)

    def recent_events_payload(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return [
            self._event_store.to_payload(event)
            for event in self.recent_events(limit=limit)
        ]
