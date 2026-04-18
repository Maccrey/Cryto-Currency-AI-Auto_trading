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


class RegimeEngine:
    """Evaluate market regime and convert it into execution constraints."""

    def evaluate(
        self,
        features: FeatureSnapshot,
        *,
        recent_loss_streak: int,
        safe_mode: bool,
    ) -> RegimeSnapshot:
        if safe_mode:
            return RegimeSnapshot(
                label="risk_off",
                score=0.0,
                size_multiplier=0.0,
                entry_allowed=False,
                reason_codes=["SAFE_MODE_ACTIVE"],
            )

        score = round(self._score(features, recent_loss_streak=recent_loss_streak), 2)
        label = self._label(score)
        reason_codes = self._reason_codes(features)
        size_multiplier = self._size_multiplier(label, recent_loss_streak=recent_loss_streak)
        entry_allowed = label != "risk_off"
        return RegimeSnapshot(
            label=label,
            score=score,
            size_multiplier=size_multiplier,
            entry_allowed=entry_allowed,
            reason_codes=reason_codes,
        )

    def _score(self, features: FeatureSnapshot, *, recent_loss_streak: int) -> float:
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
        return max(0.0, min(score, 1.0))

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
