from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMMON_LOG_FIELDS: dict[str, Any] = {}


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
            **COMMON_LOG_FIELDS,
            **event,
            "logger": record.name,
            "level": record.levelname,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with self.destination.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\n")


def configure_logging(
    log_dir: Path,
    *,
    app_name: str = "upbit-auto-trader",
    trading_mode: str = "demo",
    learning_enabled: bool = True,
) -> None:
    COMMON_LOG_FIELDS.clear()
    COMMON_LOG_FIELDS.update(
        {
            "app_name": app_name,
            "trading_mode": trading_mode,
            "learning_enabled": learning_enabled,
        },
    )
    decision_logger = logging.getLogger("decision")
    decision_logger.setLevel(logging.INFO)
    decision_logger.propagate = False
    decision_logger.handlers.clear()
    decision_logger.addHandler(JsonlFileHandler(log_dir / "decision.jsonl"))
    configure_structlog()


def configure_structlog() -> None:
    structlog = sys.modules.get("structlog")
    if structlog is None:
        try:
            import structlog as imported_structlog
        except ModuleNotFoundError:
            return
        structlog = imported_structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
