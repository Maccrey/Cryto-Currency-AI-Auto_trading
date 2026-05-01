from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.services.learning.reset import LearningDataResetService


def test_learning_data_reset_service_archives_active_log(tmp_path: Path) -> None:
    log_dir = tmp_path / "learning" / "scalping"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "learning.jsonl"
    log_path.write_text('{"event_name":"signal_generated"}\n', encoding="utf-8")
    service = LearningDataResetService(
        log_dir=log_dir,
        timestamp_provider=lambda: datetime(2026, 5, 1, 7, 30, 0),
    )

    result = service.reset()

    assert result.reset is True
    assert log_path.read_text(encoding="utf-8") == ""
    assert result.archive_path is not None
    archive_path = Path(result.archive_path)
    assert archive_path.name == "learning-20260501-073000.jsonl"
    assert archive_path.read_text(encoding="utf-8") == '{"event_name":"signal_generated"}\n'


def test_learning_data_reset_service_creates_empty_log_when_missing(tmp_path: Path) -> None:
    log_dir = tmp_path / "learning" / "short_term"
    service = LearningDataResetService(log_dir=log_dir)

    result = service.reset()

    assert result.reset is True
    assert result.archive_path is None
    assert (log_dir / "learning.jsonl").exists()
