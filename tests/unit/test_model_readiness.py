from __future__ import annotations

from pathlib import Path

from app.services.learning.model_readiness import (
    ModelTrainingReadinessService,
    ModelTrainingThresholds,
)
from app.services.learning.service import LearningEvent, LearningService


def test_model_training_readiness_reports_not_ready_when_result_labels_are_missing(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record(
        LearningEvent(
            event_name="signal_generated",
            market="KRW-XRP",
            mode="demo",
            payload={"level": "strong"},
        ),
    )

    readiness = ModelTrainingReadinessService(
        log_dir=tmp_path,
        thresholds=ModelTrainingThresholds(
            min_total_events=2,
            min_signal_events=1,
            min_fill_events=1,
            min_exit_events=1,
            min_blocked_cycles=1,
        ),
    ).build()

    assert readiness["status"] == "not_ready"
    assert readiness["completion_percent"] == 30
    assert readiness["gaps"] == {
        "total_events": 1,
        "fill_events": 1,
        "exit_events": 1,
        "blocked_cycles": 1,
    }
    assert readiness["planned_ml_extra"] == "ml"
    assert "tensorflow" in readiness["planned_packages"]


def test_model_training_readiness_reports_ready_when_thresholds_are_met(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"level": "strong"},
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"side": "buy"},
            ),
            LearningEvent(
                event_name="position_exit_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"reason_code": "STOP_LOSS_PRICE_HIT"},
            ),
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-XRP",
                mode="demo",
                payload={"status": "blocked", "reason": "AUTO_MIN_SIGNAL_LEVEL"},
            ),
        ],
    )

    readiness = ModelTrainingReadinessService(
        log_dir=tmp_path,
        thresholds=ModelTrainingThresholds(
            min_total_events=4,
            min_signal_events=1,
            min_fill_events=1,
            min_exit_events=1,
            min_blocked_cycles=1,
        ),
    ).build()

    assert readiness["status"] == "ready"
    assert readiness["completion_rate"] == 1.0
    assert readiness["completion_percent"] == 100
    assert readiness["gaps"] == {}
    assert "오프라인 학습 파이프라인" in readiness["recommended_next_step"]
