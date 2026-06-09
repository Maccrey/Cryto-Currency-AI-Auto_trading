from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.learning.jsonl import iter_jsonl_objects


REGIME_LABELS = {
    "bull": "상승장",
    "bear": "하락장",
    "box": "박스권",
}


class RawLearningLogReader:
    """Read raw learning JSONL rows from disk."""

    def read(self, jsonl_path: Path) -> list[dict[str, object]]:
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Learning log not found: {jsonl_path}")
        return list(iter_jsonl_objects(jsonl_path))


class LearningRowRegimeEnricher:
    """Attach bull/bear/box regime fields to flat learning rows."""

    def enrich(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        enriched_rows: list[dict[str, object]] = []
        last_regime_by_market: dict[str, dict[str, object]] = {}
        for row in rows:
            enriched = dict(row)
            payload = self._payload(enriched.get("payload"))
            enriched["payload"] = payload
            market = str(enriched.get("market") or payload.get("market") or "")

            regime = self._extract_regime(payload) or self._derive_from_market_window(payload)
            if regime is None and market in last_regime_by_market:
                regime = {**last_regime_by_market[market], "market_regime_source": "carried_forward"}

            self._apply_regime(enriched, payload, regime)
            if market and self._valid_state(enriched.get("market_state")):
                last_regime_by_market[market] = {
                    "market_state": enriched.get("market_state"),
                    "market_state_label": enriched.get("market_state_label"),
                    "box_range_low": enriched.get("box_range_low"),
                    "box_range_high": enriched.get("box_range_high"),
                    "market_regime_source": enriched.get("market_regime_source"),
                }
            enriched_rows.append(enriched)
        return enriched_rows

    @staticmethod
    def _payload(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _extract_regime(cls, payload: dict[str, Any]) -> dict[str, object] | None:
        state = payload.get("market_state")
        label = payload.get("market_state_label")
        source = payload.get("market_state_source") or "payload"
        if not cls._valid_state(state):
            regime = payload.get("regime")
            if isinstance(regime, dict):
                state = regime.get("market_state")
                label = regime.get("market_state_label")
                source = "payload.regime"
        if not cls._valid_state(state):
            return None
        state = str(state)
        return {
            "market_state": state,
            "market_state_label": str(label or REGIME_LABELS[state]),
            "box_range_low": cls._optional_float(payload.get("box_range_low")),
            "box_range_high": cls._optional_float(payload.get("box_range_high")),
            "market_regime_source": str(source),
        }

    @classmethod
    def _derive_from_market_window(cls, payload: dict[str, Any]) -> dict[str, object] | None:
        market_window = payload.get("market_window")
        if not isinstance(market_window, dict):
            return None
        change_pct = cls._optional_float(market_window.get("price_change_pct"))
        if change_pct is None:
            return None
        if abs(change_pct) <= 0.001:
            state = "box"
        else:
            state = "bull" if change_pct > 0 else "bear"
        return {
            "market_state": state,
            "market_state_label": REGIME_LABELS[state],
            "box_range_low": cls._optional_float(market_window.get("price_window_low")) if state == "box" else None,
            "box_range_high": cls._optional_float(market_window.get("price_window_high")) if state == "box" else None,
            "market_regime_source": "payload.market_window",
        }

    @classmethod
    def _apply_regime(
        cls,
        row: dict[str, object],
        payload: dict[str, Any],
        regime: dict[str, object] | None,
    ) -> None:
        regime = regime or {}
        state = regime.get("market_state")
        label = regime.get("market_state_label") if cls._valid_state(state) else None
        box_low = regime.get("box_range_low") if state == "box" else None
        box_high = regime.get("box_range_high") if state == "box" else None

        row["market_state"] = state if cls._valid_state(state) else None
        row["market_state_label"] = label
        row["box_range_low"] = box_low
        row["box_range_high"] = box_high
        row["market_regime_source"] = regime.get("market_regime_source") if cls._valid_state(state) else None

        if cls._valid_state(state):
            payload.setdefault("market_state", row["market_state"])
            payload.setdefault("market_state_label", row["market_state_label"])
            payload.setdefault("box_range_low", row["box_range_low"])
            payload.setdefault("box_range_high", row["box_range_high"])
            payload.setdefault("market_regime_source", row["market_regime_source"])

    @staticmethod
    def _valid_state(value: object) -> bool:
        return value in REGIME_LABELS

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class ParquetDatasetWriter:
    """Write normalized learning rows as a Parquet dataset."""

    def write(self, *, rows: list[dict[str, object]], dataset_dir: Path) -> Path:
        import pandas as pd

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
        regime_enricher: LearningRowRegimeEnricher | None = None,
    ) -> None:
        self._raw_log_reader = raw_log_reader or RawLearningLogReader()
        self._dataset_writer = dataset_writer or ParquetDatasetWriter()
        self._regime_enricher = regime_enricher or LearningRowRegimeEnricher()

    def run(self, *, jsonl_path: Path, dataset_dir: Path) -> Path:
        rows = self._raw_log_reader.read(jsonl_path)
        rows = self._regime_enricher.enrich(rows)
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
