import json
import logging
from pathlib import Path

from app.core.logging import configure_logging, get_logger


def test_decision_log_is_written_as_json(tmp_path: Path) -> None:
    configure_logging(log_dir=tmp_path)

    logger = get_logger("decision")
    logger.info(
        "signal_generated",
        extra={
            "event": {
                "event_name": "signal_generated",
                "market": "KRW-XRP",
                "mode": "demo",
                "learning_enabled": True,
            }
        },
    )

    log_file = tmp_path / "decision.jsonl"
    assert log_file.exists()

    payload = json.loads(log_file.read_text().strip())
    assert payload["event_name"] == "signal_generated"
    assert payload["market"] == "KRW-XRP"
    assert payload["mode"] == "demo"
    assert payload["learning_enabled"] is True
    assert payload["logger"] == "decision"
    assert payload["level"] == "INFO"

