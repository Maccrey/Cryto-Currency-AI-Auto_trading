from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

from app.services.signals.features import FeatureSnapshot


@dataclass(frozen=True)
class RegimeSnapshot:
    label: str
    score: float
    size_multiplier: float
    entry_allowed: bool
    reason_codes: list[str]
    market_state: str = "neutral"
    market_state_label: str = "보합"
    box_range_low: float | None = None
    box_range_high: float | None = None
    # Dynamic box range computed from rolling price history (more stable)
    dynamic_box_low: float | None = None
    dynamic_box_high: float | None = None


class RegimeScorer:
    """Reusable score calculator for regime-sensitive services."""

    def score(self, features: FeatureSnapshot, *, recent_loss_streak: int) -> float:
        positive_momentum = min(max(features.ret_30s / 0.03, 0.0), 1.0)
        positive_imbalance = min(max(features.orderbook_imbalance, 0.0), 1.0)
        tight_spread = max(0.0, 1.0 - (features.spread_bps / 20.0))

        score = 0.0
        score += min(max(features.regime_score, 0.0), 1.0) * 0.44
        score += min(max(features.liquidity_score, 0.0), 1.0) * 0.25
        score += positive_momentum * 0.15
        score += positive_imbalance * 0.06
        score += tight_spread * 0.1
        score -= min(recent_loss_streak * 0.02, 0.1)
        return round(max(0.0, min(score, 1.0)), 2)


class RegimeEngine:
    """Evaluate market regime and convert it into execution constraints.

    Enhancement: maintains a rolling price history buffer to compute
    dynamic, stable box-range boundaries using the 5th/95th percentile
    of recent prices instead of a ±volatility band around the current tick.
    """

    # Number of price ticks kept for dynamic box-range calculation
    PRICE_HISTORY_SIZE = 200
    # Min ticks needed before publishing a dynamic box range
    MIN_HISTORY_FOR_BOX = 20
    # Percentile indices used for range extraction
    BOX_LOW_PERCENTILE = 0.05
    BOX_HIGH_PERCENTILE = 0.95
    # Small buffer added outside the percentile range so entries at the edge
    # don't flip to 'outside box' on every tick
    BOX_BUFFER_PCT = 0.001

    def __init__(self, *, scorer: RegimeScorer | None = None) -> None:
        self._scorer = scorer or RegimeScorer()
        self._price_history: Deque[float] = deque(maxlen=self.PRICE_HISTORY_SIZE)

    def evaluate(
        self,
        features: FeatureSnapshot,
        *,
        recent_loss_streak: int,
        safe_mode: bool,
        current_price: float | None = None,
        observed_market_state: str | None = None,
        observed_market_state_label: str | None = None,
        observed_box_range_low: float | None = None,
        observed_box_range_high: float | None = None,
    ) -> RegimeSnapshot:
        # Always update price history so the dynamic range grows over time
        if current_price is not None and current_price > 0:
            self._price_history.append(current_price)

        if safe_mode:
            return RegimeSnapshot(
                label="risk_off",
                score=0.0,
                size_multiplier=0.0,
                entry_allowed=False,
                reason_codes=["SAFE_MODE_ACTIVE"],
                market_state="bear",
                market_state_label="하락장",
            )

        score = self._scorer.score(features, recent_loss_streak=recent_loss_streak)
        label = self._label(score)
        market_state = self._normalize_observed_market_state(observed_market_state) or self._market_state(features)

        # ── Static box range (legacy / observed) ─────────────────────────────
        if observed_market_state is not None:
            box_low, box_high = (
                (observed_box_range_low, observed_box_range_high)
                if market_state == "box"
                else (None, None)
            )
        else:
            box_low, box_high = self._box_range(features, current_price, market_state=market_state)

        # ── Dynamic box range from rolling price history ───────────────────
        dyn_low, dyn_high = self._dynamic_box_range()

        reason_codes = self._reason_codes(features)
        if observed_market_state is not None:
            reason_codes.append(f"PRICE_CARD_MARKET_STATE_{market_state.upper()}")
        if dyn_low is not None:
            reason_codes.append("DYNAMIC_BOX_RANGE_ACTIVE")

        size_multiplier = self._size_multiplier(label, recent_loss_streak=recent_loss_streak)
        entry_allowed = label != "risk_off"
        return RegimeSnapshot(
            label=label,
            score=score,
            size_multiplier=size_multiplier,
            entry_allowed=entry_allowed,
            reason_codes=reason_codes,
            market_state=market_state,
            market_state_label=observed_market_state_label or self._market_state_label(market_state),
            box_range_low=box_low,
            box_range_high=box_high,
            dynamic_box_low=dyn_low,
            dynamic_box_high=dyn_high,
        )

    @staticmethod
    def _label(score: float) -> str:
        if score >= 0.65:
            return "risk_on"
        if score >= 0.35:
            return "neutral"
        return "risk_off"

    @staticmethod
    def _size_multiplier(label: str, *, recent_loss_streak: int) -> float:
        if label == "risk_off":
            return 0.45 if recent_loss_streak < 3 else 0.3
        if label == "risk_on":
            return 1.1
        return 0.8

    @staticmethod
    def _reason_codes(features: FeatureSnapshot) -> list[str]:
        reason_codes: list[str] = []
        if features.ret_30s >= 0:
            reason_codes.append("POSITIVE_MOMENTUM")
        else:
            reason_codes.append("NEGATIVE_MOMENTUM")

        if features.spread_bps <= 10:
            reason_codes.append("TIGHT_SPREAD")
        else:
            reason_codes.append("WIDE_SPREAD")

        if features.orderbook_imbalance >= 0:
            reason_codes.append("ORDERBOOK_BUY_PRESSURE")
        else:
            reason_codes.append("ORDERBOOK_SELL_PRESSURE")

        return reason_codes

    @staticmethod
    def _market_state(features: FeatureSnapshot) -> str:
        """Classify market state using multi-factor composite rules.

        Enhancements for broader scope:
        - Bear requires BOTH a broader negative trend (ma_trend) AND negative
          orderbook imbalance.
        - Bull requires a positive broader trend (ma_trend) and either strong
          trend alignment or moderate trend + buy pressure.
        - Box (sideways) is the fall-through when neither bear nor bull
          conditions are firmly met.
        """
        # --- Bear: both broad trend and order-flow must be negative ---
        bear_trend = features.ma_trend < -0.0005
        bear_orderbook = features.orderbook_imbalance < -0.15
        if bear_trend and bear_orderbook:
            return "bear"

        # --- Bull: broad trend must be positive + momentum or buy pressure ---
        strong_bull_trend = features.ma_trend > 0.002
        moderate_bull_trend = features.ma_trend > 0.0005 and features.orderbook_imbalance > 0.12
        if strong_bull_trend or moderate_bull_trend:
            return "bull"

        # --- Sideways / box: neither firmly bull nor firmly bear ---
        return "box"

    @staticmethod
    def _normalize_observed_market_state(market_state: str | None) -> str | None:
        if market_state in {"bull", "bear", "box"}:
            return market_state
        return None

    @staticmethod
    def _market_state_label(market_state: str) -> str:
        return {
            "bull": "상승장",
            "bear": "하락장",
            "box": "박스권",
        }.get(market_state, "박스권")

    def _dynamic_box_range(self) -> tuple[float | None, float | None]:
        """Compute a stable box boundary from the rolling price-history buffer.

        Uses the 5th and 95th price percentiles (to ignore spike outliers)
        plus a small outward buffer so the box does not flip on every tick.
        Returns (None, None) until enough ticks are collected.
        """
        prices = list(self._price_history)
        if len(prices) < self.MIN_HISTORY_FOR_BOX:
            return None, None

        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        low_idx = max(int(n * self.BOX_LOW_PERCENTILE), 0)
        high_idx = min(int(n * self.BOX_HIGH_PERCENTILE), n - 1)
        low_ref = sorted_prices[low_idx]
        high_ref = sorted_prices[high_idx]

        if high_ref <= low_ref:
            return None, None

        # Add a small outward buffer
        box_low = round(low_ref * (1 - self.BOX_BUFFER_PCT), 4)
        box_high = round(high_ref * (1 + self.BOX_BUFFER_PCT), 4)
        return box_low, box_high

    @staticmethod
    def _box_range(
        features: FeatureSnapshot,
        current_price: float | None,
        *,
        market_state: str,
    ) -> tuple[float | None, float | None]:
        """Legacy static box range (used when no history is available).

        Width is based on short-term volatility — kept identical to the
        original formula so existing tests remain green. The dynamic
        history-based range (_dynamic_box_range) supersedes this
        once enough price ticks have been collected.
        """
        if market_state != "box" or current_price is None or current_price <= 0:
            return None, None
        width_pct = max(0.002, min(features.short_volatility * 2.0, 0.02))
        return round(current_price * (1 - width_pct), 4), round(current_price * (1 + width_pct), 4)
