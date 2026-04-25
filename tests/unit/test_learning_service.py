from __future__ import annotations

import json
from pathlib import Path

from app.services.learning.service import (
    LearningEvent,
    LearningEventSerializer,
    LearningService,
)


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


def test_learning_service_keeps_recent_events_in_memory(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)

    service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"level": "medium"},
            ),
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={"quantity": 120.0},
            ),
        ],
    )

    payload = service.recent_events_payload(limit=1)

    assert len(payload) == 1
    assert payload[0]["event_name"] == "position_opened"
    assert payload[0]["payload"]["quantity"] == 120.0


def test_learning_service_accepts_event_serializer(tmp_path: Path) -> None:
    service = LearningService(
        log_dir=tmp_path,
        event_serializer=LearningEventSerializer(),
    )

    service.record(
        LearningEvent(
            event_name="promotion_ready",
            market="KRW-XRP",
            mode="demo",
            payload={"profit_factor": 1.8},
        ),
    )

    row = json.loads((tmp_path / "learning.jsonl").read_text(encoding="utf-8").strip())
    assert row["event_name"] == "promotion_ready"
    assert row["payload"] == {"profit_factor": 1.8}
