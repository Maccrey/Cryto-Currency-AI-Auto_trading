from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlFileHandler(logging.Handler):
    """Persist structured events as one JSON object per line."""

    def __init__(self, destination: Path) -> None:
        super().__init__()
        self.destination = destination
        self.destination.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "event", {})
        if not isinstance(event, dict):
            event = {"message": record.getMessage()}

        payload = {
            **event,
            "logger": record.name,
            "level": record.levelname,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with self.destination.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")


def configure_logging(log_dir: Path) -> None:
    decision_logger = logging.getLogger("decision")
    decision_logger.setLevel(logging.INFO)
    decision_logger.propagate = False
    decision_logger.handlers.clear()
    decision_logger.addHandler(JsonlFileHandler(log_dir / "decision.jsonl"))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

