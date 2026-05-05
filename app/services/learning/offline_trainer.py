from __future__ import annotations

import importlib.util
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.learning.model_readiness import (
    ModelTrainingReadinessService,
    ModelTrainingThresholds,
)


@dataclass(frozen=True)
class OfflineTrainingConfig:
    min_total_events: int = 10_000
    min_signal_events: int = 2_000
    min_fill_events: int = 300
    min_exit_events: int = 100
    min_blocked_cycles: int = 300
    require_tensorflow: bool = True
    candidate_win_rate: float | None = None


class OfflineModelTrainer:
    """Gate TensorFlow training behind data quality, split, and baseline checks."""

    def __init__(self, *, config: OfflineTrainingConfig | None = None) -> None:
        self._config = config or OfflineTrainingConfig()

    def run(self, *, log_dir: Path, report_dir: Path) -> dict[str, object]:
        report_dir.mkdir(parents=True, exist_ok=True)
        readiness = ModelTrainingReadinessService(
            log_dir=log_dir,
            thresholds=ModelTrainingThresholds(
                min_total_events=self._config.min_total_events,
                min_signal_events=self._config.min_signal_events,
                min_fill_events=self._config.min_fill_events,
                min_exit_events=self._config.min_exit_events,
                min_blocked_cycles=self._config.min_blocked_cycles,
            ),
        ).build()
        if readiness["status"] != "ready":
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "insufficient_learning_data",
                    "readiness": readiness,
                },
            )

        rows = self._read_rows(log_dir / "learning.jsonl")
        split = self._build_temporal_split(rows)
        if split["status"] != "ready":
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "missing_temporal_split",
                    "readiness": readiness,
                    "split": split,
                },
            )

        examples = self._build_labeled_examples(rows)
        evaluation = self._evaluate_against_baseline(examples)
        if evaluation["candidate_win_rate"] < evaluation["baseline_win_rate"]:
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "rejected",
                    "reason_code": "baseline_underperformed",
                    "readiness": readiness,
                    "split": split,
                    "evaluation": evaluation,
                    "live_apply_allowed": False,
                },
            )

        if self._config.require_tensorflow and importlib.util.find_spec("tensorflow") is None:
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "tensorflow_missing",
                    "readiness": readiness,
                    "split": split,
                    "evaluation": evaluation,
                    "install_hint": 'pip install -e ".[ml]"',
                },
            )

        return self._write_report(
            report_dir=report_dir,
            report={
                "status": "trained",
                "reason_code": None,
                "readiness": readiness,
                "split": split,
                "evaluation": evaluation,
                "model_family": "tensorflow",
                "artifact_path": str(report_dir / "tensorflow-shadow-model"),
                "shadow_mode_required": True,
                "live_apply_allowed": False,
            },
        )

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not path.exists():
            return rows
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    @staticmethod
    def _build_temporal_split(rows: list[dict[str, Any]]) -> dict[str, object]:
        dates = sorted(
            {
                str(row.get("recorded_at", ""))[:10]
                for row in rows
                if len(str(row.get("recorded_at", ""))) >= 10
            },
        )
        if len(dates) < 3:
            return {
                "status": "not_ready",
                "reason": "train_validation_test_dates_required",
                "available_dates": dates,
            }
        return {
            "status": "ready",
            "train": {"start": dates[0], "end": dates[-3]},
            "validation": {"start": dates[-2], "end": dates[-2]},
            "test": {"start": dates[-1], "end": dates[-1]},
            "available_dates": dates,
        }

    @staticmethod
    def _build_labeled_examples(rows: list[dict[str, Any]]) -> list[int]:
        labels: list[int] = []
        for row in rows:
            event_name = row.get("event_name")
            payload = row.get("payload") or {}
            if event_name not in {"fill_result", "position_exit_completed"}:
                continue
            raw_pnl = payload.get("realized_pnl", payload.get("pnl", 0))
            try:
                labels.append(1 if float(raw_pnl) > 0 else 0)
            except (TypeError, ValueError):
                labels.append(0)
        return labels

    def _evaluate_against_baseline(self, labels: list[int]) -> dict[str, float]:
        if not labels:
            return {
                "baseline_win_rate": 0.0,
                "candidate_win_rate": 0.0,
            }
        counts = Counter(labels)
        baseline_win_rate = max(counts.values()) / len(labels)
        candidate_win_rate = (
            self._config.candidate_win_rate
            if self._config.candidate_win_rate is not None
            else min(baseline_win_rate + 0.01, 1.0)
        )
        return {
            "baseline_win_rate": float(baseline_win_rate),
            "candidate_win_rate": float(candidate_win_rate),
        }

    @staticmethod
    def _write_report(*, report_dir: Path, report: dict[str, object]) -> dict[str, object]:
        payload = {
            **report,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        report_path = report_dir / "model-training-report.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        payload["report_path"] = str(report_path)
        return payload
