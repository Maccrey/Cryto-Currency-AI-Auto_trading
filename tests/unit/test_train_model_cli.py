from pathlib import Path

from app.cli.train_model import main
from app.services.learning.service import LearningEvent, LearningService


def test_train_model_cli_returns_refusal_exit_code_for_insufficient_data(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "--log-dir",
            str(tmp_path / "logs"),
            "--report-dir",
            str(tmp_path / "reports"),
            "--min-total-events",
            "1",
        ],
    )

    output = capsys.readouterr().out

    assert exit_code == 2
    assert '"reason_code": "insufficient_learning_data"' in output


def test_train_model_cli_writes_shadow_report_when_gates_pass(tmp_path: Path, capsys) -> None:
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
                    payload={"score": 0.8, "level": "strong"},
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

    exit_code = main(
        [
            "--log-dir",
            str(log_dir),
            "--report-dir",
            str(report_dir),
            "--min-total-events",
            "12",
            "--min-signal-events",
            "3",
            "--min-fill-events",
            "3",
            "--min-exit-events",
            "3",
            "--min-blocked-cycles",
            "3",
            "--skip-tensorflow-check",
        ],
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "trained"' in output
    assert (report_dir / "shadow-predictions.jsonl").exists()
