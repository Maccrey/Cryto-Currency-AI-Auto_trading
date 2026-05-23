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


class LearningEventSerializer:
    """Serialize learning events into stable JSONL row payloads."""

    def to_payload(self, event: LearningEvent) -> dict[str, Any]:
        payload = asdict(event)
        payload["schema_version"] = 2
        return payload

    def to_json_line(self, event: LearningEvent) -> str:
        return json.dumps(self.to_payload(event), ensure_ascii=True)


class JsonlLearningExporter:
    """Append learning events to a single JSONL file."""

    def __init__(
        self,
        *,
        log_dir: Path,
        event_serializer: LearningEventSerializer | None = None,
    ) -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "learning.jsonl"
        self._event_serializer = event_serializer or LearningEventSerializer()

    def export(self, event: LearningEvent) -> None:
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(self._event_serializer.to_json_line(event))
            handle.write("\n")


class MarketObservationExporter:
    """Append raw market observations used for replay and rule analysis."""

    def __init__(self, *, log_dir: Path) -> None:
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "market-observations.jsonl"

    def export(self, payload: dict[str, Any]) -> None:
        row = dict(payload)
        row["schema_version"] = 1
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True))
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

    def clear(self) -> None:
        self._events.clear()

    @staticmethod
    def to_payload(event: LearningEvent) -> dict[str, Any]:
        return asdict(event)


class LearningService:
    """Record normalized learning events for every execution mode."""

    def __init__(
        self,
        *,
        log_dir: Path,
        trading_profile: str = "scalping",
        event_store: LearningEventStore | None = None,
        event_serializer: LearningEventSerializer | None = None,
    ) -> None:
        self._trading_profile = trading_profile
        self._event_serializer = event_serializer or LearningEventSerializer()
        self._exporter = JsonlLearningExporter(
            log_dir=log_dir,
            event_serializer=self._event_serializer,
        )
        self._market_observation_exporter = MarketObservationExporter(log_dir=log_dir)
        self._event_store = event_store or LearningEventStore()

    def record(self, event: LearningEvent) -> None:
        payload = dict(event.payload)
        payload.setdefault("trading_profile", self._trading_profile)
        event = LearningEvent(
            event_name=event.event_name,
            market=event.market,
            mode=event.mode,
            payload=payload,
            recorded_at=event.recorded_at,
        )
        self._exporter.export(event)
        self._event_store.record(event)

    def record_many(self, events: list[LearningEvent]) -> None:
        for event in events:
            self.record(event)

    def record_market_observation(self, payload: dict[str, Any]) -> None:
        self._market_observation_exporter.export(payload)

    def recent_events(self, *, limit: int | None = None) -> list[LearningEvent]:
        return self._event_store.list_events(limit=limit)

    def recent_events_payload(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return [
            self._event_store.to_payload(event)
            for event in self.recent_events(limit=limit)
        ]

    def clear_recent_events(self) -> None:
        self._event_store.clear()
