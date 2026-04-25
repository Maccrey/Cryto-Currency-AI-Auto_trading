from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class RawLearningLogReader:
    """Read raw learning JSONL rows from disk."""

    def read(self, jsonl_path: Path) -> list[dict[str, object]]:
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Learning log not found: {jsonl_path}")
        return [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


class ParquetDatasetWriter:
    """Write normalized learning rows as a Parquet dataset."""

    def write(self, *, rows: list[dict[str, object]], dataset_dir: Path) -> Path:
        frame = pd.json_normalize(rows, sep=".")
        output_path = dataset_dir / "learning.parquet"
        frame.to_parquet(output_path, index=False)
        return output_path


class DatasetPipeline:
    """Convert raw learning logs into dataset files."""

    def __init__(
        self,
        *,
        raw_log_reader: RawLearningLogReader | None = None,
        dataset_writer: ParquetDatasetWriter | None = None,
    ) -> None:
        self._raw_log_reader = raw_log_reader or RawLearningLogReader()
        self._dataset_writer = dataset_writer or ParquetDatasetWriter()

    def run(self, *, jsonl_path: Path, dataset_dir: Path) -> Path:
        rows = self._raw_log_reader.read(jsonl_path)
        return self._dataset_writer.write(rows=rows, dataset_dir=dataset_dir)


class DatasetExporter:
    """Convert learning JSONL into a flat Parquet dataset."""

    def __init__(
        self,
        *,
        dataset_dir: Path,
        dataset_pipeline: DatasetPipeline | None = None,
    ) -> None:
        self._dataset_dir = dataset_dir
        self._dataset_dir.mkdir(parents=True, exist_ok=True)
        self._dataset_pipeline = dataset_pipeline or DatasetPipeline()

    def export(self, jsonl_path: Path) -> Path:
        return self._dataset_pipeline.run(
            jsonl_path=jsonl_path,
            dataset_dir=self._dataset_dir,
        )
