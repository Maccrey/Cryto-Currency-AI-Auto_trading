from __future__ import annotations

from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class FeatureSnapshot:
    ret_1s: float
    ret_5s: float
    ret_30s: float
    volume_multiple: float
    traded_value_multiple: float
    spread_bps: float
    orderbook_imbalance: float
    short_volatility: float
    regime_score: float
    liquidity_score: float


class MarketFeatureCalculator:
    """Compute momentum and liquidity features from recent market observations."""

    def calculate(
        self,
        *,
        prices: list[float],
        traded_values: list[float],
        spread_bps: float,
        orderbook_imbalance: float,
        liquidity_score: float,
        regime_score: float,
    ) -> FeatureSnapshot:
        if len(prices) < 2:
            raise ValueError("At least two prices are required")
        if len(traded_values) < 2:
            raise ValueError("At least two traded_values are required")

        ret_1s = _return(prices[-2], prices[-1])
        ret_5s = _return(prices[0], prices[-1])
        ret_30s = _return(prices[0], prices[-1])
        comparison_window = traded_values[-3:-1] if len(traded_values) >= 3 else traded_values[:-1]
        volume_multiple = traded_values[-1] / (sum(comparison_window) / len(comparison_window))
        traded_value_multiple = volume_multiple
        short_volatility = _average_absolute_return(
            [_return(a, b) for a, b in zip(prices[:-1], prices[1:])],
        )

        return FeatureSnapshot(
            ret_1s=ret_1s,
            ret_5s=ret_5s,
            ret_30s=ret_30s,
            volume_multiple=volume_multiple,
            traded_value_multiple=traded_value_multiple,
            spread_bps=spread_bps,
            orderbook_imbalance=orderbook_imbalance,
            short_volatility=short_volatility,
            regime_score=regime_score,
            liquidity_score=liquidity_score,
        )


def _return(start_price: float, end_price: float) -> float:
    return log(end_price / start_price)


def _average_absolute_return(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(abs(value) for value in values) / len(values)
