from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class LearningDataResetResult:
    reset: bool
    log_path: str
    archive_path: str | None
    message: str
    extra_files_reset: list[str] = field(default_factory=list)


# 학습 데이터 삭제·아카이브 대상 추가 파일 목록
# learning.jsonl 이외에 진단 로그 파일이 추가될 때 여기에 추가한다.
EXTRA_LOG_FILES = [
    "market-observations.jsonl",     # 시장 관측 로그
    "rule-change-history.jsonl",     # 룰 변경 이력
    "rule-review-state.json",        # 룰 리뷰 상태
]


class LearningDataResetService:
    """Archive the active profile learning log so the profile can learn from a clean file.

    reset(): learning.jsonl + EXTRA_LOG_FILES 를 모두 타임스탬프 아카이브로 이동
    delete(): learning.jsonl + EXTRA_LOG_FILES 를 모두 비운다
    """

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

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _extra_log_paths(self) -> list[Path]:
        """EXTRA_LOG_FILES 에 해당하는 Path 목록 반환 (존재하는 파일만)."""
        return [
            self._log_dir / name
            for name in EXTRA_LOG_FILES
            if (self._log_dir / name).exists()
        ]

    # ── 공개 메서드 ──────────────────────────────────────────────────────────

    def reset(self) -> LearningDataResetResult:
        """학습 데이터를 아카이브로 이동하고 파일을 비운다."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_dir / "learning.jsonl"

        stamp = self._timestamp_provider().strftime("%Y%m%d-%H%M%S")
        profile = self._log_dir.name
        archive_dir = self._archive_root / profile
        archive_dir.mkdir(parents=True, exist_ok=True)

        # learning.jsonl 처리
        if not log_path.exists() or log_path.stat().st_size == 0:
            log_path.write_text("", encoding="utf-8")
            archive_path = None
            main_message = "learning data already empty"
        else:
            archive_path = archive_dir / f"learning-{stamp}.jsonl"
            log_path.replace(archive_path)
            log_path.write_text("", encoding="utf-8")
            archive_path = str(archive_path)
            main_message = "learning data archived and reset"

        # 추가 로그 파일 처리
        extra_archived: list[str] = []
        for extra_path in self._extra_log_paths():
            dest = archive_dir / f"{extra_path.name}-{stamp}"
            extra_path.replace(dest)
            extra_path.write_text("", encoding="utf-8")
            extra_archived.append(extra_path.name)

        return LearningDataResetResult(
            reset=True,
            log_path=str(log_path),
            archive_path=archive_path,
            message=f"{main_message}" + (f"; also archived: {', '.join(extra_archived)}" if extra_archived else ""),
            extra_files_reset=extra_archived,
        )

    def delete(self) -> LearningDataResetResult:
        """학습 데이터를 영구 삭제(파일 비우기)한다."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_dir / "learning.jsonl"
        deleted = log_path.exists() and log_path.stat().st_size > 0
        log_path.write_text("", encoding="utf-8")

        # 추가 로그 파일도 함께 삭제
        extra_deleted: list[str] = []
        for extra_path in self._extra_log_paths():
            extra_path.write_text("", encoding="utf-8")
            extra_deleted.append(extra_path.name)

        base_msg = "learning data permanently deleted" if deleted else "learning data already empty"
        return LearningDataResetResult(
            reset=True,
            log_path=str(log_path),
            archive_path=None,
            message=base_msg + (f"; also deleted: {', '.join(extra_deleted)}" if extra_deleted else ""),
            extra_files_reset=extra_deleted,
        )
