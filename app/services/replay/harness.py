from __future__ import annotations

from dataclasses import dataclass

from app.services.replay.loader import ReplayTick
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator


@dataclass(frozen=True)
class ReplayResult:
    timestamp: str
    signal_level: str
    signal_score: float
    blocked: bool


class ReplayHarness:
    """Replay historical ticks through feature and signal services."""

    def __init__(self) -> None:
        self._feature_calculator = MarketFeatureCalculator()
        self._signal_engine = SignalEngine()

    def run(self, ticks: list[ReplayTick]) -> list[ReplayResult]:
        results: list[ReplayResult] = []
        prices: list[float] = []
        traded_values: list[float] = []

        for tick in ticks:
            prices.append(tick.price)
            traded_values.append(tick.traded_value)
            if len(prices) < 3:
                continue

            features = self._feature_calculator.calculate(
                prices=prices[-4:],
                traded_values=traded_values[-4:],
                spread_bps=tick.spread_bps,
                orderbook_imbalance=tick.orderbook_imbalance,
                liquidity_score=tick.liquidity_score,
                regime_score=tick.regime_score,
            )
            decision = self._signal_engine.evaluate(features)
            results.append(
                ReplayResult(
                    timestamp=tick.timestamp,
                    signal_level=decision.level,
                    signal_score=decision.score,
                    blocked=decision.blocked,
                ),
            )

        return results
