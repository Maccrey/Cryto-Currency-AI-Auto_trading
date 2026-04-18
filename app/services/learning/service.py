from __future__ import annotations

import json
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


class LearningService:
    """Record normalized learning events for every execution mode."""

    def __init__(self, *, log_dir: Path) -> None:
        self._exporter = JsonlLearningExporter(log_dir=log_dir)

    def record(self, event: LearningEvent) -> None:
        self._exporter.export(event)

    def record_many(self, events: list[LearningEvent]) -> None:
        for event in events:
            self.record(event)
