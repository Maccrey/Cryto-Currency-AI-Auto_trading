from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SidewaysRiskConfig:
    enabled: bool = True
    price_range_pct: float = 0.002
    traded_value_range_pct: float = 0.003
    max_avg_abs_return_pct: float = 0.001
    scale_in_min_discount_pct: float = 0.003


@dataclass(frozen=True)
class SidewaysRiskDecision:
    allowed: bool
    reason_code: str | None
    is_sideways: bool
    price_range_pct: float
    traded_value_range_pct: float
    avg_abs_return_pct: float
    min_scale_in_price: float | None = None


class SidewaysMarketRiskGuard:
    """Block low-edge entries while price and traded value are stagnant."""

    def __init__(self, config: SidewaysRiskConfig | None = None) -> None:
        self._config = config or SidewaysRiskConfig()

    def check(
        self,
        *,
        prices: list[float],
        traded_values: list[float],
        current_price: float,
        signal_level: str,
        relaxed_signal: bool,
        position_entry_price: float | None = None,
    ) -> SidewaysRiskDecision:
        metrics = self._metrics(prices=prices, traded_values=traded_values)
        is_sideways = self._is_sideways(metrics)
        base = {
            "is_sideways": is_sideways,
            "price_range_pct": metrics["price_range_pct"],
            "traded_value_range_pct": metrics["traded_value_range_pct"],
            "avg_abs_return_pct": metrics["avg_abs_return_pct"],
        }
        if not self._config.enabled or not is_sideways:
            return SidewaysRiskDecision(allowed=True, reason_code=None, **base)

        if position_entry_price is not None and position_entry_price > 0:
            if signal_level == "weak":
                return SidewaysRiskDecision(
                    allowed=False,
                    reason_code="SIDEWAYS_WEAK_SCALE_IN_BLOCK",
                    **base,
                )
            min_scale_in_price = round(position_entry_price * (1 - self._config.scale_in_min_discount_pct), 4)
            if current_price > min_scale_in_price:
                return SidewaysRiskDecision(
                    allowed=False,
                    reason_code="SIDEWAYS_SCALE_IN_PRICE_UNCHANGED",
                    min_scale_in_price=min_scale_in_price,
                    **base,
                )

        if relaxed_signal and signal_level == "weak":
            return SidewaysRiskDecision(
                allowed=False,
                reason_code="SIDEWAYS_WEAK_RELAXED_ENTRY_BLOCK",
                **base,
            )

        return SidewaysRiskDecision(allowed=True, reason_code=None, **base)

    def _is_sideways(self, metrics: dict[str, float]) -> bool:
        return (
            metrics["price_range_pct"] <= self._config.price_range_pct
            and metrics["traded_value_range_pct"] <= self._config.traded_value_range_pct
            and metrics["avg_abs_return_pct"] <= self._config.max_avg_abs_return_pct
        )

    @staticmethod
    def _metrics(*, prices: list[float], traded_values: list[float]) -> dict[str, float]:
        price_range_pct = _range_pct(prices)
        traded_value_range_pct = _range_pct(traded_values)
        returns = [
            abs((end - start) / start)
            for start, end in zip(prices[:-1], prices[1:])
            if start > 0
        ]
        avg_abs_return_pct = 0.0 if not returns else sum(returns) / len(returns)
        return {
            "price_range_pct": round(price_range_pct, 6),
            "traded_value_range_pct": round(traded_value_range_pct, 6),
            "avg_abs_return_pct": round(avg_abs_return_pct, 6),
        }


def _range_pct(values: list[float]) -> float:
    positive_values = [value for value in values if value > 0]
    if len(positive_values) < 2:
        return 1.0
    midpoint = sum(positive_values) / len(positive_values)
    if midpoint <= 0:
        return 1.0
    return (max(positive_values) - min(positive_values)) / midpoint
