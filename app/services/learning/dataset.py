from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class DatasetExporter:
    """Convert learning JSONL into a flat Parquet dataset."""

    def __init__(self, *, dataset_dir: Path) -> None:
        self._dataset_dir = dataset_dir
        self._dataset_dir.mkdir(parents=True, exist_ok=True)

    def export(self, jsonl_path: Path) -> Path:
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Learning log not found: {jsonl_path}")

        rows = [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        frame = pd.json_normalize(rows, sep=".")
        output_path = self._dataset_dir / "learning.parquet"
        frame.to_parquet(output_path, index=False)
        return output_path
