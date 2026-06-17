from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.learning.service import LearningEvent
from app.services.signals.features import FeatureSnapshot


@dataclass(frozen=True)
class SignalDecision:
    level: str
    score: float
    blocked: bool
    reason_codes: list[str]


class SignalReasonCodeGenerator:
    """Build stable reason codes for signal decisions."""

    def blocked(self, features: FeatureSnapshot) -> list[str]:
        reason_codes: list[str] = []
        if features.liquidity_score < 0.2:
            reason_codes.append("LOW_LIQUIDITY_BLOCKED")
        if features.ret_1s < -0.004:
            reason_codes.append("MICRO_MOMENTUM_REVERSAL_BLOCKED")
        if features.short_volatility > 0.03:
            reason_codes.append("EXCESSIVE_SHORT_VOLATILITY_BLOCKED")
        if features.rsi_14 >= 82 and features.bollinger_position >= 0.96:
            reason_codes.append("TECHNICAL_OVERBOUGHT_BLOCKED")
        if (
            features.price_position_20 >= 0.92
            and features.ret_1s <= 0
            and features.trend_efficiency_20 < 0.35
        ):
            reason_codes.append("HIGH_POSITION_REVERSAL_BLOCKED")
        return reason_codes

    def generated(self, features: FeatureSnapshot) -> list[str]:
        reason_codes = []
        if features.ret_30s >= 0.02:
            reason_codes.append("MOMENTUM_BREAKOUT")
        if features.traded_value_multiple >= 1.8:
            reason_codes.append("VALUE_ACCELERATION")
        if features.orderbook_imbalance > 0.2:
            reason_codes.append("ORDERBOOK_SUPPORT")
        if features.macd_histogram > 0 and features.ma_trend > 0:
            reason_codes.append("MACD_MA_TREND_CONFIRMATION")
        if 42 <= features.rsi_14 <= 68 and features.stochastic_k >= 55:
            reason_codes.append("RSI_STOCHASTIC_ENTRY_WINDOW")
        if features.bollinger_position <= 0.22 and features.rsi_14 >= 35:
            reason_codes.append("BOLLINGER_PULLBACK_ENTRY")
        if (
            features.rebound_from_low_20 >= 0.003
            and features.trend_efficiency_20 >= 0.15
            and features.ret_5s > 0
        ):
            reason_codes.append("LOW_REBOUND_CONFIRMATION")
        return reason_codes


class SignalEngine:
    """Translate feature snapshots into normalized entry signals."""

    def __init__(
        self,
        *,
        learning_service=None,
        trading_mode: str = "demo",
        market: str = "unknown",
        reason_code_generator: SignalReasonCodeGenerator | None = None,
    ) -> None:
        self._learning_service = learning_service
        self._trading_mode = trading_mode
        self._market = market
        self._reason_code_generator = reason_code_generator or SignalReasonCodeGenerator()

    def evaluate(self, features: FeatureSnapshot) -> SignalDecision:
        block_reasons = self._reason_code_generator.blocked(features)
        if block_reasons:
            decision = SignalDecision(
                level="weak",
                score=round(self._score(features), 2),
                blocked=True,
                reason_codes=block_reasons,
            )
            self._record_learning_event(features, decision)
            return decision

        score = round(self._score(features), 2)
        level = self._score_to_level(score)

        decision = SignalDecision(
            level=level,
            score=score,
            blocked=False,
            reason_codes=self._reason_code_generator.generated(features),
        )
        self._record_learning_event(features, decision)
        return decision

    def _score(self, features: FeatureSnapshot) -> float:
        momentum_component = min(max(features.ret_30s / 0.035, 0.0), 1.0) * 0.3
        short_momentum_component = min(max(features.ret_5s / 0.012, 0.0), 1.0) * 0.15
        value_component = min(features.traded_value_multiple / 2.5, 1.0) * 0.2
        imbalance_component = min(max(features.orderbook_imbalance, 0.0), 1.0) * 0.2
        regime_component = min(max(features.regime_score, 0.0), 1.0) * 0.1
        volatility_component = max(0.0, 1.0 - min(features.short_volatility / 0.02, 1.0)) * 0.05
        technical_component = (self._technical_score(features) - 0.5) * 0.15
        return (
            momentum_component
            + short_momentum_component
            + value_component
            + imbalance_component
            + regime_component
            + volatility_component
            + technical_component
        )

    @staticmethod
    def _technical_score(features: FeatureSnapshot) -> float:
        rsi_window = 1.0 - min(abs(features.rsi_14 - 55.0) / 45.0, 1.0)
        macd_signal = 1.0 if features.macd_histogram > 0 else 0.35
        ma_signal = 1.0 if features.ma_trend > 0 else 0.35
        bollinger_signal = 1.0 - min(abs(features.bollinger_position - 0.45) / 0.55, 1.0)
        stochastic_signal = min(max(features.stochastic_k / 100.0, 0.0), 1.0)
        return max(
            min(
                (rsi_window * 0.28)
                + (macd_signal * 0.24)
                + (ma_signal * 0.2)
                + (bollinger_signal * 0.16)
                + (stochastic_signal * 0.12),
                1.0,
            ),
            0.0,
        )

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.85:
            return "very_strong"
        if score >= 0.65:
            return "strong"
        if score >= 0.4:
            return "medium"
        return "weak"

    def _record_learning_event(
        self,
        features: FeatureSnapshot,
        decision: SignalDecision,
    ) -> None:
        if self._learning_service is None:
            return
        self._learning_service.record(
            LearningEvent(
                event_name="signal_generated",
                market=self._market,
                mode=self._trading_mode,
                payload={
                    "level": decision.level,
                    "score": decision.score,
                    "blocked": decision.blocked,
                    "reason_codes": decision.reason_codes,
                    "regime_score": features.regime_score,
                    "liquidity_score": features.liquidity_score,
                    "market_features": asdict(features),
                    "technical_indicators": {
                        "rsi_14": features.rsi_14,
                        "macd_histogram": features.macd_histogram,
                        "bollinger_position": features.bollinger_position,
                        "ma_trend": features.ma_trend,
                        "stochastic_k": features.stochastic_k,
                        "price_position_20": features.price_position_20,
                        "drawdown_from_high_20": features.drawdown_from_high_20,
                        "rebound_from_low_20": features.rebound_from_low_20,
                        "trend_efficiency_20": features.trend_efficiency_20,
                    },
                },
            ),
        )
