from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.learning.dataset import DatasetExporter
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
        ],
    )

    exporter = DatasetExporter(dataset_dir=dataset_dir)
    parquet_path = exporter.export(log_dir / "learning.jsonl")

    assert parquet_path == dataset_dir / "learning.parquet"
    assert parquet_path.exists()

    frame = pd.read_parquet(parquet_path)
    assert list(frame["event_name"]) == ["signal_generated", "fill_result"]
    assert list(frame["market"]) == ["KRW-XRP", "KRW-XRP"]
    assert frame.loc[0, "payload.level"] == "strong"
    assert frame.loc[0, "payload.score"] == 0.72
    assert frame.loc[1, "payload.side"] == "buy"
    assert frame.loc[1, "payload.filled_price"] == 820.0


def test_dataset_exporter_raises_on_missing_jsonl(tmp_path: Path) -> None:
    exporter = DatasetExporter(dataset_dir=tmp_path / "dataset")

    try:
        exporter.export(tmp_path / "missing.jsonl")
    except FileNotFoundError as exc:
        assert "missing.jsonl" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing learning jsonl")

