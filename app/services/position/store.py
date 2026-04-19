from __future__ import annotations

from dataclasses import asdict

from app.services.risk.stop_loss import PositionSnapshot


class CurrentPositionStore:
    """Hold the latest active position for runtime inspection."""

    def __init__(self) -> None:
        self._position: PositionSnapshot | None = None

    def save(self, position: PositionSnapshot) -> PositionSnapshot:
        self._position = position
        return position

    def get(self) -> PositionSnapshot | None:
        return self._position

    def clear(self) -> None:
        self._position = None

    @staticmethod
    def to_payload(position: PositionSnapshot) -> dict[str, object]:
        return asdict(position)
