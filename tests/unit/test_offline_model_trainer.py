from pathlib import Path

from app.services.learning.offline_trainer import (
    OfflineModelTrainer,
    OfflineTrainingConfig,
)
from app.services.learning.service import LearningEvent, LearningService


def test_offline_trainer_refuses_when_learning_data_is_insufficient(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    LearningService(log_dir=log_dir).record(
        LearningEvent(
            event_name="signal_generated",
            market="KRW-XRP",
            mode="demo",
            payload={"score": 0.72},
            recorded_at="2026-05-01T00:00:00+00:00",
        ),
    )

    report = OfflineModelTrainer(
        config=OfflineTrainingConfig(
            min_total_events=2,
            min_signal_events=1,
            min_fill_events=1,
            min_exit_events=1,
            min_blocked_cycles=1,
            require_tensorflow=False,
        ),
    ).run(log_dir=log_dir, report_dir=report_dir)

    assert report["status"] == "refused"
    assert report["reason_code"] == "insufficient_learning_data"
    assert report["readiness"]["status"] == "not_ready"
    assert Path(str(report["report_path"])).exists()


def test_offline_trainer_refuses_without_train_validation_test_split(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    service = LearningService(log_dir=log_dir)
    service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"score": 0.72},
                recorded_at="2026-05-01T00:00:00+00:00",
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"realized_pnl": 1200},
                recorded_at="2026-05-01T01:00:00+00:00",
            ),
            LearningEvent(
                event_name="position_exit_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"realized_pnl": -400},
                recorded_at="2026-05-01T02:00:00+00:00",
            ),
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-XRP",
                mode="demo",
                payload={"status": "blocked"},
                recorded_at="2026-05-01T03:00:00+00:00",
            ),
        ],
    )

    report = OfflineModelTrainer(
        config=OfflineTrainingConfig(
            min_total_events=4,
            min_signal_events=1,
            min_fill_events=1,
            min_exit_events=1,
            min_blocked_cycles=1,
            require_tensorflow=False,
        ),
    ).run(log_dir=log_dir, report_dir=report_dir)

    assert report["status"] == "refused"
    assert report["reason_code"] == "missing_temporal_split"
    assert report["split"]["status"] == "not_ready"


def test_offline_trainer_rejects_model_worse_than_baseline(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    service = LearningService(log_dir=log_dir)
    for day in range(1, 4):
        service.record_many(
            [
                LearningEvent(
                    event_name="signal_generated",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"score": 0.6 + day / 100},
                    recorded_at=f"2026-05-0{day}T00:00:00+00:00",
                ),
                LearningEvent(
                    event_name="fill_result",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"realized_pnl": 1000},
                    recorded_at=f"2026-05-0{day}T01:00:00+00:00",
                ),
                LearningEvent(
                    event_name="position_exit_completed",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"realized_pnl": 1000},
                    recorded_at=f"2026-05-0{day}T02:00:00+00:00",
                ),
                LearningEvent(
                    event_name="auto_trade_cycle",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"status": "blocked"},
                    recorded_at=f"2026-05-0{day}T03:00:00+00:00",
                ),
            ],
        )

    report = OfflineModelTrainer(
        config=OfflineTrainingConfig(
            min_total_events=12,
            min_signal_events=3,
            min_fill_events=3,
            min_exit_events=3,
            min_blocked_cycles=3,
            require_tensorflow=False,
            candidate_win_rate=0.2,
        ),
    ).run(log_dir=log_dir, report_dir=report_dir)

    assert report["status"] == "rejected"
    assert report["reason_code"] == "baseline_underperformed"
    assert report["evaluation"]["candidate_win_rate"] < report["evaluation"]["baseline_win_rate"]


def test_offline_trainer_writes_shadow_report_when_gates_pass(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    report_dir = tmp_path / "reports"
    service = LearningService(log_dir=log_dir)
    for day in range(1, 4):
        service.record_many(
            [
                LearningEvent(
                    event_name="signal_generated",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"score": 0.6 + day / 100},
                    recorded_at=f"2026-05-0{day}T00:00:00+00:00",
                ),
                LearningEvent(
                    event_name="fill_result",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"realized_pnl": 1000 if day != 3 else -100},
                    recorded_at=f"2026-05-0{day}T01:00:00+00:00",
                ),
                LearningEvent(
                    event_name="position_exit_completed",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"realized_pnl": 1000 if day != 3 else -100},
                    recorded_at=f"2026-05-0{day}T02:00:00+00:00",
                ),
                LearningEvent(
                    event_name="auto_trade_cycle",
                    market="KRW-XRP",
                    mode="demo",
                    payload={"status": "blocked"},
                    recorded_at=f"2026-05-0{day}T03:00:00+00:00",
                ),
            ],
        )

    report = OfflineModelTrainer(
        config=OfflineTrainingConfig(
            min_total_events=12,
            min_signal_events=3,
            min_fill_events=3,
            min_exit_events=3,
            min_blocked_cycles=3,
            require_tensorflow=False,
            candidate_win_rate=0.9,
        ),
    ).run(log_dir=log_dir, report_dir=report_dir)

    assert report["status"] == "trained"
    assert report["shadow_mode_required"] is True
    assert report["live_apply_allowed"] is False
    assert Path(str(report["shadow_predictions_path"])).exists()
    assert Path(str(report["report_path"])).exists()

    shadow_lines = Path(str(report["shadow_predictions_path"])).read_text(encoding="utf-8").splitlines()
    assert len(shadow_lines) == 3
    assert '"model_decision": "observe"' in shadow_lines[0]
    assert '"live_apply_allowed": false' in shadow_lines[0]
