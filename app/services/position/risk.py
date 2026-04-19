from __future__ import annotations

from dataclasses import asdict

from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator


class PositionRiskService:
    """Evaluate stored position state against active risk rules."""

    def __init__(
        self,
        *,
        position_store: CurrentPositionStore,
        hard_stop_monitor: HardStopMonitor,
        post_entry_validator: PostEntryValidator,
    ) -> None:
        self._position_store = position_store
        self._hard_stop_monitor = hard_stop_monitor
        self._post_entry_validator = post_entry_validator

    def evaluate(
        self,
        *,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> dict[str, object]:
        position = self._position_store.get()
        if position is None:
            return {
                "status": "empty",
                "position": None,
                "hard_stop": None,
                "post_entry": None,
            }

        hard_stop = self._hard_stop_monitor.evaluate(
            position=position,
            current_price=current_price,
        )
        post_entry = self._post_entry_validator.evaluate(
            position=position,
            current_price=current_price,
            elapsed_sec=elapsed_sec,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        return {
            "status": "ok",
            "position": self._position_store.to_payload(position),
            "hard_stop": asdict(hard_stop),
            "post_entry": asdict(post_entry),
        }
