from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class LearningDataResetResult:
    reset: bool
    log_path: str
    archive_path: str | None
    message: str


class LearningDataResetService:
    """Archive the active profile learning log so the profile can learn from a clean file."""

    def __init__(
        self,
        *,
        log_dir: Path,
        archive_root: Path | None = None,
        timestamp_provider=None,
    ) -> None:
        self._log_dir = log_dir
        self._archive_root = archive_root or log_dir.parent / "reset_archive"
        self._timestamp_provider = timestamp_provider or datetime.now

    def reset(self) -> LearningDataResetResult:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_dir / "learning.jsonl"
        if not log_path.exists() or log_path.stat().st_size == 0:
            log_path.write_text("", encoding="utf-8")
            return LearningDataResetResult(
                reset=True,
                log_path=str(log_path),
                archive_path=None,
                message="learning data already empty",
            )

        stamp = self._timestamp_provider().strftime("%Y%m%d-%H%M%S")
        profile = self._log_dir.name
        archive_dir = self._archive_root / profile
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"learning-{stamp}.jsonl"
        log_path.replace(archive_path)
        log_path.write_text("", encoding="utf-8")
        return LearningDataResetResult(
            reset=True,
            log_path=str(log_path),
            archive_path=str(archive_path),
            message="learning data archived and reset",
        )

    def delete(self) -> LearningDataResetResult:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_dir / "learning.jsonl"
        deleted = log_path.exists() and log_path.stat().st_size > 0
        log_path.write_text("", encoding="utf-8")
        return LearningDataResetResult(
            reset=True,
            log_path=str(log_path),
            archive_path=None,
            message="learning data permanently deleted" if deleted else "learning data already empty",
        )
