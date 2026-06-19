"""Market transition detector and dynamic box-range tracker.

This module detects market-state transitions (bear→bull and bull→bear)
using composite technical indicators rather than a single signal.
It also maintains a sliding-window price history to compute stable
box-range boundaries for sideways markets.

Transition score: 0.0 (no evidence) → 1.0 (strong evidence of transition)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from app.services.signals.features import FeatureSnapshot


@dataclass(frozen=True)
class TransitionState:
    """Result of one transition-detection evaluation."""

    # ── Bear-to-bull ──────────────────────────────────────────────────────────
    bear_to_bull_score: float
    """Composite score for bear→bull transition (0.0 – 1.0)."""
    bear_to_bull_confirmed: bool
    """True when score ≥ confirmation threshold."""

    # ── Bull-to-bear ──────────────────────────────────────────────────────────
    bull_to_bear_score: float
    """Composite score for bull→bear transition (0.0 – 1.0)."""
    bull_to_bear_confirmed: bool
    """True when score ≥ confirmation threshold."""

    # ── Dynamic box range ─────────────────────────────────────────────────────
    dynamic_box_low: float | None
    """Stable lower boundary for box-range calculated from price history."""
    dynamic_box_high: float | None
    """Stable upper boundary for box-range calculated from price history."""
    dynamic_box_position: float | None
    """Current price position within [dynamic_box_low, dynamic_box_high] (0→1)."""

    # ── Meta ──────────────────────────────────────────────────────────────────
    prev_rsi: float | None
    """RSI at the previous evaluation (for cross detection)."""
    prev_macd_histogram: float | None
    """MACD histogram at the previous evaluation (for cross detection)."""
    reason_codes: list[str] = field(default_factory=list)


class MarketTransitionDetector:
    """Detect market-state transitions and track dynamic box range.

    All parameters are tunable without changing internal logic.

    Parameters
    ----------
    bear_to_bull_threshold:
        Minimum composite score to confirm a bear→bull transition. Default 0.60.
    bull_to_bear_threshold:
        Minimum composite score to confirm a bull→bear transition. Default 0.60.
    price_history_size:
        Number of ticks kept for dynamic box-range computation. Default 100.
    box_low_pct:
        Lower boundary = recent_low × (1 + box_low_pct). Default 0.0 (exact low).
    box_high_pct:
        Upper boundary = recent_high × (1 - box_high_pct). Default 0.0 (exact high).
    """

    def __init__(
        self,
        *,
        bear_to_bull_threshold: float = 0.60,
        bull_to_bear_threshold: float = 0.60,
        price_history_size: int = 100,
        box_low_pct: float = 0.002,
        box_high_pct: float = 0.002,
    ) -> None:
        self._bear_to_bull_threshold = bear_to_bull_threshold
        self._bull_to_bear_threshold = bull_to_bear_threshold
        self._price_history: Deque[float] = deque(maxlen=price_history_size)
        self._box_low_pct = box_low_pct
        self._box_high_pct = box_high_pct

        # Previous-tick memory for cross detection
        self._prev_rsi: float | None = None
        self._prev_macd_histogram: float | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def evaluate(
        self,
        features: FeatureSnapshot,
        *,
        current_price: float,
        current_market_state: str,
    ) -> TransitionState:
        """Evaluate transition signals and update price history.

        Parameters
        ----------
        features:
            Latest feature snapshot from MarketFeatureCalculator.
        current_price:
            Latest execution price (must be > 0).
        current_market_state:
            Regime engine's classification: ``"bull"``, ``"bear"``, or ``"box"``.
        """
        if current_price > 0:
            self._price_history.append(current_price)

        b2b_score, b2b_codes = self._score_bear_to_bull(features, current_market_state)
        bu2be_score, bu2be_codes = self._score_bull_to_bear(features, current_market_state)

        b2b_confirmed = b2b_score >= self._bear_to_bull_threshold
        bu2be_confirmed = bu2be_score >= self._bull_to_bear_threshold

        box_low, box_high = self._dynamic_box_range()
        box_pos = self._box_position(current_price, box_low, box_high)

        state = TransitionState(
            bear_to_bull_score=round(b2b_score, 4),
            bear_to_bull_confirmed=b2b_confirmed,
            bull_to_bear_score=round(bu2be_score, 4),
            bull_to_bear_confirmed=bu2be_confirmed,
            dynamic_box_low=box_low,
            dynamic_box_high=box_high,
            dynamic_box_position=box_pos,
            prev_rsi=self._prev_rsi,
            prev_macd_histogram=self._prev_macd_histogram,
            reason_codes=b2b_codes + bu2be_codes,
        )

        # Update memory for next tick
        self._prev_rsi = features.rsi_14
        self._prev_macd_histogram = features.macd_histogram

        return state

    def reset(self) -> None:
        """Clear all stored state (use when re-starting a test session)."""
        self._price_history.clear()
        self._prev_rsi = None
        self._prev_macd_histogram = None

    # ──────────────────────────────────────────────────────────────────────────
    # Bear-to-bull transition scoring
    # ──────────────────────────────────────────────────────────────────────────

    def _score_bear_to_bull(
        self,
        f: FeatureSnapshot,
        market_state: str,
    ) -> tuple[float, list[str]]:
        """Compute a composite bear→bull transition score.

        Scoring components (total weight = 1.0):
          RSI oversold recovery      0.25
          MACD histogram cross up    0.20
          MA trend recovery          0.20
          Positive momentum          0.20
          Orderbook buy pressure     0.15
        """
        codes: list[str] = []
        score = 0.0

        # 1. RSI oversold recovery (was below 35, now rising above 35)
        rsi_recovery = self._prev_rsi is not None and self._prev_rsi < 35.0 and f.rsi_14 >= 35.0
        rsi_oversold_low = f.rsi_14 < 38.0  # still oversold = partial credit
        if rsi_recovery:
            score += 0.25
            codes.append("B2B_RSI_OVERSOLD_RECOVERY")
        elif rsi_oversold_low and f.rsi_14 > (self._prev_rsi or 50.0):
            score += 0.12
            codes.append("B2B_RSI_LOW_RISING")

        # 2. MACD histogram: negative → positive cross OR rising from below zero
        macd_cross_up = (
            self._prev_macd_histogram is not None
            and self._prev_macd_histogram < 0.0
            and f.macd_histogram >= 0.0
        )
        macd_improving = (
            self._prev_macd_histogram is not None
            and f.macd_histogram > self._prev_macd_histogram
            and f.macd_histogram < 0.0
        )
        if macd_cross_up:
            score += 0.20
            codes.append("B2B_MACD_CROSS_UP")
        elif macd_improving:
            score += 0.10
            codes.append("B2B_MACD_IMPROVING")

        # 3. MA trend recovery (short MA regaining strength vs long MA)
        if f.ma_trend >= 0.0:
            score += 0.20
            codes.append("B2B_MA_TREND_POSITIVE")
        elif f.ma_trend >= -0.001:
            score += 0.10
            codes.append("B2B_MA_TREND_NEAR_ZERO")

        # 4. Positive short-term momentum
        if f.ret_30s > 0.002:
            score += 0.20
            codes.append("B2B_STRONG_POSITIVE_MOMENTUM")
        elif f.ret_30s > 0.0:
            score += 0.10
            codes.append("B2B_POSITIVE_MOMENTUM")

        # 5. Orderbook: buyers gaining dominance
        if f.orderbook_imbalance >= 0.05:
            score += 0.15
            codes.append("B2B_ORDERBOOK_BUY_PRESSURE")
        elif f.orderbook_imbalance >= -0.05:
            score += 0.07
            codes.append("B2B_ORDERBOOK_NEUTRAL")

        # Bonus: rebound from low confirms continuation
        if f.rebound_from_low_20 >= 0.005:
            score += 0.08
            codes.append("B2B_REBOUND_FROM_LOW")
            score = min(score, 1.0)

        # Penalty: still in deep bear territory → reduce confidence
        if market_state == "bear" and f.bollinger_position >= 0.6:
            # Price is high in bear = dead-cat bounce risk
            score *= 0.75

        return round(min(score, 1.0), 4), codes

    # ──────────────────────────────────────────────────────────────────────────
    # Bull-to-bear transition scoring
    # ──────────────────────────────────────────────────────────────────────────

    def _score_bull_to_bear(
        self,
        f: FeatureSnapshot,
        market_state: str,
    ) -> tuple[float, list[str]]:
        """Compute a composite bull→bear transition score.

        Scoring components (total weight = 1.0):
          RSI overbought reversal    0.25
          MACD histogram cross down  0.20
          MA trend deterioration     0.20
          Negative momentum          0.20
          Orderbook sell pressure    0.15
        """
        codes: list[str] = []
        score = 0.0

        # 1. RSI overbought reversal (was above 65, now falling below 65)
        rsi_reversal = self._prev_rsi is not None and self._prev_rsi > 65.0 and f.rsi_14 <= 65.0
        rsi_high_falling = f.rsi_14 > 60.0 and (self._prev_rsi or 50.0) > f.rsi_14
        if rsi_reversal:
            score += 0.25
            codes.append("BU2BE_RSI_OVERBOUGHT_REVERSAL")
        elif rsi_high_falling:
            score += 0.12
            codes.append("BU2BE_RSI_HIGH_FALLING")

        # 2. MACD histogram: positive → negative cross OR falling from above zero
        macd_cross_down = (
            self._prev_macd_histogram is not None
            and self._prev_macd_histogram > 0.0
            and f.macd_histogram <= 0.0
        )
        macd_deteriorating = (
            self._prev_macd_histogram is not None
            and f.macd_histogram < self._prev_macd_histogram
            and f.macd_histogram > 0.0
        )
        if macd_cross_down:
            score += 0.20
            codes.append("BU2BE_MACD_CROSS_DOWN")
        elif macd_deteriorating:
            score += 0.10
            codes.append("BU2BE_MACD_DETERIORATING")

        # 3. MA trend deterioration
        if f.ma_trend <= -0.001:
            score += 0.20
            codes.append("BU2BE_MA_TREND_NEGATIVE")
        elif f.ma_trend <= 0.0:
            score += 0.10
            codes.append("BU2BE_MA_TREND_NEAR_ZERO")

        # 4. Negative short-term momentum
        if f.ret_30s < -0.003:
            score += 0.20
            codes.append("BU2BE_STRONG_NEGATIVE_MOMENTUM")
        elif f.ret_30s < 0.0:
            score += 0.10
            codes.append("BU2BE_NEGATIVE_MOMENTUM")

        # 5. Orderbook: sellers gaining dominance
        if f.orderbook_imbalance <= -0.10:
            score += 0.15
            codes.append("BU2BE_ORDERBOOK_SELL_PRESSURE")
        elif f.orderbook_imbalance <= 0.0:
            score += 0.07
            codes.append("BU2BE_ORDERBOOK_NEUTRAL_WEAK")

        # Bonus: drawdown accelerating from recent high
        if f.drawdown_from_high_20 <= -0.005:
            score += 0.08
            codes.append("BU2BE_DRAWDOWN_ACCELERATING")
            score = min(score, 1.0)

        # Penalty: still in strong bull momentum → reduce confidence
        if market_state == "bull" and f.bollinger_position <= 0.4:
            # Price is still low in bull = pullback risk, not reversal
            score *= 0.75

        return round(min(score, 1.0), 4), codes

    # ──────────────────────────────────────────────────────────────────────────
    # Dynamic box range
    # ──────────────────────────────────────────────────────────────────────────

    def _dynamic_box_range(self) -> tuple[float | None, float | None]:
        """Compute stable box boundaries from the price history window.

        Uses the 5th-percentile low (ignores spike lows) and the
        95th-percentile high (ignores spike highs) with a small buffer.
        Falls back to exact min/max when history is too small to sort.
        """
        prices = list(self._price_history)
        if len(prices) < 10:
            return None, None

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        # Use 5th / 95th percentile to ignore extreme outliers
        low_idx = max(int(n * 0.05), 0)
        high_idx = min(int(n * 0.95), n - 1)
        low_ref = sorted_prices[low_idx]
        high_ref = sorted_prices[high_idx]

        if high_ref <= low_ref:
            return None, None

        box_low = round(low_ref * (1 - self._box_low_pct), 4)
        box_high = round(high_ref * (1 + self._box_high_pct), 4)
        return box_low, box_high

    @staticmethod
    def _box_position(
        price: float,
        box_low: float | None,
        box_high: float | None,
    ) -> float | None:
        """Normalised position of price within the dynamic box (0 = low, 1 = high)."""
        if box_low is None or box_high is None or box_high <= box_low or price <= 0:
            return None
        return round(max(min((price - box_low) / (box_high - box_low), 1.0), 0.0), 4)
