from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.services.risk.stop_loss import PositionSnapshot


class CurrentPositionStore:
    """Hold the latest active position for runtime inspection."""

    def __init__(self, *, storage_path: Path | None = None) -> None:
        self._storage_path = storage_path
        self._position: PositionSnapshot | None = None
        self._load()

    def save(self, position: PositionSnapshot) -> PositionSnapshot:
        self._position = position
        self._persist()
        return position

    def get(self) -> PositionSnapshot | None:
        return self._position

    def clear(self) -> None:
        self._position = None
        self._persist()

    @staticmethod
    def to_payload(position: PositionSnapshot) -> dict[str, object]:
        return asdict(position)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if payload is None:
            self._position = None
            return
        if not isinstance(payload, dict):
            return
        try:
            self._position = PositionSnapshot(
                market=str(payload["market"]),
                signal_level=str(payload["signal_level"]),
                entry_price=float(payload["entry_price"]),
                quantity=float(payload["quantity"]),
                stop_loss_price=float(payload["stop_loss_price"]),
                stop_loss_pct=float(payload["stop_loss_pct"]),
                validation_window_sec=int(payload["validation_window_sec"]),
                min_expected_return_pct=float(payload["min_expected_return_pct"]),
                stop_loss_reason=None if payload.get("stop_loss_reason") is None else str(payload["stop_loss_reason"]),
            )
        except (KeyError, TypeError, ValueError):
            self._position = None

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = None if self._position is None else asdict(self._position)
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
