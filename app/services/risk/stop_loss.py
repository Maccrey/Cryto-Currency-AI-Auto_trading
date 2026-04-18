from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSnapshot:
    market: str
    signal_level: str
    entry_price: float
    quantity: float
    stop_loss_price: float
    stop_loss_pct: float
    validation_window_sec: int
    min_expected_return_pct: float
    stop_loss_reason: str | None


@dataclass(frozen=True)
class BuyExecutionAlertPayload:
    market: str
    signal_level: str
    buy_amount: float
    quantity: float
    buy_ratio: float
    entry_price: float
    stop_loss_price: float
    executed_at: str


class StopLossInjector:
    """Attach stop-loss metadata to every filled buy position."""

    def __init__(
        self,
        *,
        stop_loss_by_signal: dict[str, float],
        validation_window_sec: int,
        min_expected_return_pct: float,
    ) -> None:
        self._stop_loss_by_signal = dict(stop_loss_by_signal)
        self._validation_window_sec = validation_window_sec
        self._min_expected_return_pct = min_expected_return_pct

    def inject(
        self,
        *,
        market: str,
        signal_level: str,
        entry_price: float,
        quantity: float,
    ) -> PositionSnapshot:
        stop_loss_pct = self._stop_loss_by_signal[signal_level]
        stop_loss_price = round(entry_price * (1 - stop_loss_pct), 2)
        return PositionSnapshot(
            market=market,
            signal_level=signal_level,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss_price=stop_loss_price,
            stop_loss_pct=stop_loss_pct,
            validation_window_sec=self._validation_window_sec,
            min_expected_return_pct=self._min_expected_return_pct,
            stop_loss_reason=None,
        )

    @staticmethod
    def build_buy_alert_payload(
        position: PositionSnapshot,
        *,
        buy_amount: float,
        buy_ratio: float,
        executed_at: str,
    ) -> BuyExecutionAlertPayload:
        return BuyExecutionAlertPayload(
            market=position.market,
            signal_level=position.signal_level,
            buy_amount=buy_amount,
            quantity=position.quantity,
            buy_ratio=buy_ratio,
            entry_price=position.entry_price,
            stop_loss_price=position.stop_loss_price,
            executed_at=executed_at,
        )
