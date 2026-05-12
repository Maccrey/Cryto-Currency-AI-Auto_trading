from __future__ import annotations

from dataclasses import dataclass

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
    """Evaluate market regime and convert it into execution constraints."""

    def __init__(self, *, scorer: RegimeScorer | None = None) -> None:
        self._scorer = scorer or RegimeScorer()

    def evaluate(
        self,
        features: FeatureSnapshot,
        *,
        recent_loss_streak: int,
        safe_mode: bool,
        current_price: float | None = None,
    ) -> RegimeSnapshot:
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
        market_state = self._market_state(features)
        box_low, box_high = self._box_range(features, current_price, market_state=market_state)
        reason_codes = self._reason_codes(features)
        size_multiplier = self._size_multiplier(label, recent_loss_streak=recent_loss_streak)
        entry_allowed = label != "risk_off"
        return RegimeSnapshot(
            label=label,
            score=score,
            size_multiplier=size_multiplier,
            entry_allowed=entry_allowed,
            reason_codes=reason_codes,
            market_state=market_state,
            market_state_label=self._market_state_label(market_state),
            box_range_low=box_low,
            box_range_high=box_high,
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
        if abs(features.ret_30s) <= 0.0025 and abs(features.orderbook_imbalance) <= 0.08:
            return "box"
        if features.ret_30s < -0.004 or features.orderbook_imbalance < -0.18:
            return "bear"
        if features.ret_30s > 0.004 or features.orderbook_imbalance > 0.18:
            return "bull"
        return "box"

    @staticmethod
    def _market_state_label(market_state: str) -> str:
        return {
            "bull": "상승장",
            "bear": "하락장",
            "box": "박스권",
        }.get(market_state, "박스권")

    @staticmethod
    def _box_range(
        features: FeatureSnapshot,
        current_price: float | None,
        *,
        market_state: str,
    ) -> tuple[float | None, float | None]:
        if market_state != "box" or current_price is None or current_price <= 0:
            return None, None
        width_pct = max(0.002, min(features.short_volatility * 2.0, 0.02))
        return round(current_price * (1 - width_pct), 4), round(current_price * (1 + width_pct), 4)
