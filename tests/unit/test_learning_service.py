from __future__ import annotations

import json
from pathlib import Path

from app.services.learning.service import LearningEvent, LearningService


def test_learning_service_persists_decision_event_as_jsonl(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)

    event = LearningEvent(
        event_name="signal_generated",
        market="KRW-XRP",
        mode="demo",
        payload={"level": "strong", "score": 0.72},
    )

    service.record(event)

    log_path = tmp_path / "learning.jsonl"
    assert log_path.exists()
    row = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert row["event_name"] == "signal_generated"
    assert row["market"] == "KRW-XRP"
    assert row["mode"] == "demo"
    assert row["payload"] == {"level": "strong", "score": 0.72}


def test_learning_service_persists_fill_and_restart_events(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)

    events = [
        LearningEvent(
            event_name="fill_result",
            market="KRW-XRP",
            mode="live",
            payload={"side": "buy", "filled_price": 820.0},
        ),
        LearningEvent(
            event_name="restart_detected",
            market="KRW-XRP",
            mode="live",
            payload={"cause": "process_restart", "safe_mode": True},
        ),
    ]

    service.record_many(events)

    rows = [
        json.loads(line)
        for line in (tmp_path / "learning.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event_name"] for row in rows] == ["fill_result", "restart_detected"]
    assert rows[1]["payload"]["safe_mode"] is True

