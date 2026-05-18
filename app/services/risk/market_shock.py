from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketShockConfig:
    enabled: bool = True
    crash_change_pct: float = -0.015
    surge_change_pct: float = 0.020
    recovery_change_pct: float = 0.003
    recovery_confirmation_ticks: int = 3


@dataclass(frozen=True)
class MarketShockDecision:
    allowed: bool
    reason_code: str | None
    shock_state: str
    recent_change_pct: float
    last_return_pct: float
    recovery_count: int
    alert_type: str | None = None


class MarketShockRiskGuard:
    """Block entries during abrupt drops until a real recovery is visible."""

    def __init__(self, config: MarketShockConfig | None = None) -> None:
        self._config = config or MarketShockConfig()
        self._crash_active = False
        self._recovery_count = 0

    def check(self, *, prices: list[float]) -> MarketShockDecision:
        recent_change_pct = _recent_change_pct(prices)
        last_return_pct = _last_return_pct(prices)
        alert_type = self._alert_type(recent_change_pct=recent_change_pct)

        if not self._config.enabled:
            return MarketShockDecision(
                allowed=True,
                reason_code=None,
                shock_state="disabled",
                recent_change_pct=recent_change_pct,
                last_return_pct=last_return_pct,
                recovery_count=self._recovery_count,
                alert_type=alert_type,
            )

        if recent_change_pct <= self._config.crash_change_pct:
            self._crash_active = True
            self._recovery_count = 0

        if self._crash_active:
            if last_return_pct > 0 and recent_change_pct >= self._config.recovery_change_pct:
                self._recovery_count += 1
            else:
                self._recovery_count = 0
            if self._recovery_count >= self._config.recovery_confirmation_ticks:
                self._crash_active = False
                return MarketShockDecision(
                    allowed=True,
                    reason_code=None,
                    shock_state="recovered",
                    recent_change_pct=recent_change_pct,
                    last_return_pct=last_return_pct,
                    recovery_count=self._recovery_count,
                    alert_type=alert_type,
                )
            return MarketShockDecision(
                allowed=False,
                reason_code="MARKET_CRASH_OBSERVE_ONLY",
                shock_state="crash_observe_only",
                recent_change_pct=recent_change_pct,
                last_return_pct=last_return_pct,
                recovery_count=self._recovery_count,
                alert_type=alert_type,
            )

        return MarketShockDecision(
            allowed=True,
            reason_code=None,
            shock_state="surge" if recent_change_pct >= self._config.surge_change_pct else "normal",
            recent_change_pct=recent_change_pct,
            last_return_pct=last_return_pct,
            recovery_count=self._recovery_count,
            alert_type=alert_type,
        )

    def _alert_type(self, *, recent_change_pct: float) -> str | None:
        if recent_change_pct <= self._config.crash_change_pct:
            return "crash"
        if recent_change_pct >= self._config.surge_change_pct:
            return "surge"
        return None


def _recent_change_pct(prices: list[float]) -> float:
    positive_prices = [price for price in prices if price > 0]
    if len(positive_prices) < 2 or positive_prices[0] <= 0:
        return 0.0
    return round((positive_prices[-1] - positive_prices[0]) / positive_prices[0], 6)


def _last_return_pct(prices: list[float]) -> float:
    positive_prices = [price for price in prices if price > 0]
    if len(positive_prices) < 2 or positive_prices[-2] <= 0:
        return 0.0
    return round((positive_prices[-1] - positive_prices[-2]) / positive_prices[-2], 6)
