from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.learning.dataset import (
    DatasetExporter,
    DatasetPipeline,
    ParquetDatasetWriter,
    RawLearningLogReader,
)
from app.services.learning.service import LearningEvent, LearningService


def test_dataset_exporter_converts_learning_jsonl_to_parquet(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    dataset_dir = tmp_path / "dataset"
    learning_service = LearningService(log_dir=log_dir)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"level": "strong", "score": 0.72},
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"side": "buy", "filled_price": 820.0},
            ),
            LearningEvent(
                event_name="promotion_review_completed",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "demo_days": 16,
                    "total_trades": 132,
                    "profit_factor": 1.31,
                    "max_drawdown": 0.051,
                    "stoploss_failures": 0,
                    "approval_granted": True,
                    "approved_by": "manual_review",
                    "activated_at": "2026-04-19T10:30:00+09:00",
                    "evaluation_status": "READY_FOR_REVIEW",
                    "approved": False,
                    "rejection_reasons": [],
                    "live_enabled": True,
                    "safe_mode_entry": True,
                    "reason_code": None,
                },
            ),
        ],
    )

    exporter = DatasetExporter(dataset_dir=dataset_dir)
    parquet_path = exporter.export(log_dir / "learning.jsonl")

    assert parquet_path == dataset_dir / "learning.parquet"
    assert parquet_path.exists()

    frame = pd.read_parquet(parquet_path)
    assert list(frame["event_name"]) == [
        "signal_generated",
        "fill_result",
        "promotion_review_completed",
    ]
    assert list(frame["market"]) == ["KRW-XRP", "KRW-XRP", "KRW-XRP"]
    assert frame.loc[0, "payload.level"] == "strong"
    assert frame.loc[0, "payload.score"] == 0.72
    assert frame.loc[1, "payload.side"] == "buy"
    assert frame.loc[1, "payload.filled_price"] == 820.0
    assert frame.loc[2, "payload.demo_days"] == 16
    assert frame.loc[2, "payload.total_trades"] == 132
    assert frame.loc[2, "payload.profit_factor"] == 1.31
    assert frame.loc[2, "payload.evaluation_status"] == "READY_FOR_REVIEW"
    assert frame.loc[2, "payload.live_enabled"] is True
    assert frame.loc[2, "payload.safe_mode_entry"] is True
    assert pd.isna(frame.loc[2, "payload.reason_code"])


def test_dataset_exporter_raises_on_missing_jsonl(tmp_path: Path) -> None:
    exporter = DatasetExporter(dataset_dir=tmp_path / "dataset")

    try:
        exporter.export(tmp_path / "missing.jsonl")
    except FileNotFoundError as exc:
        assert "missing.jsonl" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing learning jsonl")


def test_dataset_exporter_accepts_raw_log_dataset_pipeline(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "learning.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_name": "signal_generated",
                        "market": "KRW-XRP",
                        "mode": "demo",
                        "payload": {"level": "strong"},
                        "recorded_at": "2026-04-19T10:00:00+00:00",
                    },
                ),
                "",
            ],
        ),
        encoding="utf-8",
    )
    dataset_dir = tmp_path / "dataset"
    exporter = DatasetExporter(
        dataset_dir=dataset_dir,
        dataset_pipeline=DatasetPipeline(
            raw_log_reader=RawLearningLogReader(),
            dataset_writer=ParquetDatasetWriter(),
        ),
    )

    parquet_path = exporter.export(jsonl_path)

    frame = pd.read_parquet(parquet_path)
    assert parquet_path == dataset_dir / "learning.parquet"
    assert frame.loc[0, "event_name"] == "signal_generated"
    assert frame.loc[0, "payload.level"] == "strong"
