from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import TYPE_CHECKING

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeEngine, RegimeSnapshot
from app.services.signals.engine import SignalDecision, SignalEngine
from app.services.signals.features import FeatureSnapshot, MarketFeatureCalculator
from app.services.sizing.engine import SizingDecision, SizingEngine

if TYPE_CHECKING:
    from app.services.trading.market_transition import TransitionState


@dataclass(frozen=True)
class TradeDecisionRequest:
    prices: list[float]
    traded_values: list[float]
    spread_bps: float
    orderbook_imbalance: float
    liquidity_score: float
    regime_score: float
    current_price: float
    slippage_bps: float
    portfolio: PortfolioState
    safe_mode: bool
    recent_loss_streak: int
    relax_fee_edge: bool = False
    external_context_weight: float = 1.0
    observed_market_state: str | None = None
    observed_market_state_label: str | None = None
    observed_box_range_low: float | None = None
    observed_box_range_high: float | None = None
    target_daily_return_pct: float = 0.005


@dataclass(frozen=True)
class TradeDecisionResult:
    features: FeatureSnapshot
    signal: SignalDecision
    regime: RegimeSnapshot
    sizing: SizingDecision
    # Optional transition state (populated when MarketTransitionDetector is active)
    transition_state: TransitionState | None = field(default=None)


class TradeDecisionService:
    """Evaluate a complete entry decision from market data to order sizing."""

    def __init__(
        self,
        *,
        feature_calculator: MarketFeatureCalculator,
        signal_engine: SignalEngine,
        regime_engine: RegimeEngine,
        sizing_engine: SizingEngine,
    ) -> None:
        self._feature_calculator = feature_calculator
        self._signal_engine = signal_engine
        self._regime_engine = regime_engine
        self._sizing_engine = sizing_engine
        self._runtime_rule_overrides: dict[str, float] = {}

    def set_demo_rule_overrides(self, overrides: dict[str, float]) -> dict[str, float]:
        """Store bounded in-memory overrides applied only by the demo runner."""
        allowed = {
            "technical_trend_confirmation_boost": (0.0, 0.05),
            "bearish_entry_score_multiplier": (0.80, 1.0),
            "external_context_bullish_multiplier": (1.0, 1.02),
        }
        applied: dict[str, float] = {}
        for key, value in overrides.items():
            if key not in allowed:
                continue
            lower, upper = allowed[key]
            applied[key] = round(min(max(float(value), lower), upper), 4)
        self._runtime_rule_overrides.update(applied)
        return applied

    def evaluate(self, request: TradeDecisionRequest) -> TradeDecisionResult:
        features = self._feature_calculator.calculate(
            prices=request.prices,
            traded_values=request.traded_values,
            spread_bps=request.spread_bps,
            orderbook_imbalance=request.orderbook_imbalance,
            liquidity_score=request.liquidity_score,
            regime_score=request.regime_score,
        )
        signal = self._signal_engine.evaluate(features)
        signal = self._apply_technical_trend_confirmation(signal, features)
        signal = self._apply_external_context(signal, request.external_context_weight)
        signal = self._apply_daily_target(signal, request.target_daily_return_pct)
        regime = self._regime_engine.evaluate(
            features,
            recent_loss_streak=request.recent_loss_streak,
            safe_mode=request.safe_mode,
            current_price=request.current_price,
            observed_market_state=request.observed_market_state,
            observed_market_state_label=request.observed_market_state_label,
            observed_box_range_low=request.observed_box_range_low,
            observed_box_range_high=request.observed_box_range_high,
        )
        signal = self._apply_market_opportunity(signal, regime, features)
        signal = self._apply_bearish_size_reduction(signal, regime)
        sizing = self._sizing_engine.size_entry(
            request.portfolio,
            signal,
            regime,
            current_price=request.current_price,
            spread_bps=request.spread_bps,
            slippage_bps=request.slippage_bps,
            relax_fee_edge=request.relax_fee_edge,
        )
        return TradeDecisionResult(
            features=features,
            signal=signal,
            regime=regime,
            sizing=sizing,
        )

    def _apply_technical_trend_confirmation(
        self,
        signal: SignalDecision,
        features: FeatureSnapshot,
    ) -> SignalDecision:
        boost = self._runtime_rule_overrides.get("technical_trend_confirmation_boost", 0.0)
        if signal.blocked or boost <= 0 or features.macd_histogram <= 0 or features.ma_trend <= 0:
            return signal
        score = round(min(signal.score + boost, 1.0), 2)
        reasons = list(signal.reason_codes)
        if "TECHNICAL_TREND_CONFIRMATION_APPLIED" not in reasons:
            reasons.append("TECHNICAL_TREND_CONFIRMATION_APPLIED")
        return replace(signal, score=score, level=self._score_to_level(score), reason_codes=reasons)

    def _apply_bearish_size_reduction(self, signal: SignalDecision, regime: RegimeSnapshot) -> SignalDecision:
        multiplier = self._runtime_rule_overrides.get("bearish_entry_score_multiplier", 1.0)
        if signal.blocked or regime.market_state != "bear" or multiplier >= 1.0:
            return signal
        score = round(signal.score * multiplier, 2)
        reasons = list(signal.reason_codes)
        if "TECHNICAL_BEARISH_SIZE_REDUCTION_APPLIED" not in reasons:
            reasons.append("TECHNICAL_BEARISH_SIZE_REDUCTION_APPLIED")
        return replace(signal, score=score, level=self._score_to_level(score), reason_codes=reasons)

    def _apply_external_context(self, signal: SignalDecision, weight: float) -> SignalDecision:
        if float(weight or 1.0) > 1.0:
            weight = float(weight) * self._runtime_rule_overrides.get("external_context_bullish_multiplier", 1.0)
        normalized_weight = max(min(float(weight or 1.0), 1.25), 0.75)
        if normalized_weight == 1.0:
            return signal
        adjusted_score = round(max(min(signal.score * normalized_weight, 1.0), 0.0), 2)
        reason_codes = list(signal.reason_codes)
        if normalized_weight > 1.0 and "EXTERNAL_CONTEXT_BULLISH_BOOST" not in reason_codes:
            reason_codes.append("EXTERNAL_CONTEXT_BULLISH_BOOST")
        if normalized_weight < 1.0 and "EXTERNAL_CONTEXT_RISK_OFF" not in reason_codes:
            reason_codes.append("EXTERNAL_CONTEXT_RISK_OFF")
        return replace(
            signal,
            score=adjusted_score,
            level=TradeDecisionService._score_to_level(adjusted_score),
            reason_codes=reason_codes,
        )

    @staticmethod
    def _apply_daily_target(signal: SignalDecision, target_daily_return_pct: float) -> SignalDecision:
        target = max(min(float(target_daily_return_pct or 0.005), 0.02), 0.001)
        adjusted_score = round(max(min(signal.score * min(1.08, 1.0 + max(target - 0.005, 0.0)), 1.0), 0.0), 2)
        reason_codes = list(signal.reason_codes)
        if "TARGET_DAILY_RETURN_0_5PCT" not in reason_codes:
            reason_codes.append("TARGET_DAILY_RETURN_0_5PCT")
        return replace(
            signal,
            score=adjusted_score,
            level=TradeDecisionService._score_to_level(adjusted_score),
            reason_codes=reason_codes,
        )

    @staticmethod
    def _apply_market_opportunity(
        signal: SignalDecision,
        regime: RegimeSnapshot,
        features: FeatureSnapshot,
    ) -> SignalDecision:
        if signal.blocked or signal.level != "weak":
            return signal
        score_floor = 0.0
        reason_code = None
        if regime.market_state == "bull" and TradeDecisionService._bull_participation_signal(features):
            score_floor = 0.40
            reason_code = "BULL_MARKET_PARTICIPATION_BOOST"
        elif regime.market_state == "box" and TradeDecisionService._box_lower_range_signal(regime, features):
            # Enhanced: use dynamic box range if available
            score_floor = 0.42
            reason_code = "BOX_RANGE_VALUE_ENTRY_BOOST"
        elif regime.market_state == "bear" and TradeDecisionService._bear_rebound_signal(features):
            # Bear rebound: stronger boost so transition entries get through
            score_floor = 0.45
            reason_code = "BEAR_REBOUND_PARTICIPATION"
        if reason_code is None or signal.score >= score_floor:
            return signal
        reason_codes = list(signal.reason_codes)
        if reason_code not in reason_codes:
            reason_codes.append(reason_code)
        adjusted_score = round(score_floor, 2)
        return replace(
            signal,
            score=adjusted_score,
            level=TradeDecisionService._score_to_level(adjusted_score),
            reason_codes=reason_codes,
        )

    @staticmethod
    def _bull_participation_signal(features: FeatureSnapshot) -> bool:
        technical_support = (
            features.macd_histogram >= -0.0005
            and features.ma_trend >= -0.0005
            and features.rsi_14 <= 78.0
            and features.bollinger_position <= 0.95
            and features.price_position_20 <= 0.92
        )
        flow_support = (
            features.ret_5s >= 0.0
            or features.orderbook_imbalance >= -0.08
            or features.trend_efficiency_20 >= 0.15
        )
        return technical_support and flow_support

    @staticmethod
    def _box_lower_range_signal(regime: RegimeSnapshot, features: FeatureSnapshot) -> bool:
        if regime.box_range_low is None or regime.box_range_high is None:
            return False
        return (
            features.bollinger_position <= 0.38
            and features.rsi_14 >= 32.0
            and features.orderbook_imbalance >= -0.12
        )

    @staticmethod
    def _bear_rebound_signal(features: FeatureSnapshot) -> bool:
        return (
            features.ret_5s > 0.0
            and features.rebound_from_low_20 >= 0.004
            and features.trend_efficiency_20 >= 0.15
            and features.price_position_20 <= 0.72
            and features.orderbook_imbalance >= -0.05
            and features.rsi_14 <= 60.0
            and features.bollinger_position <= 0.88
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

    @staticmethod
    def to_payload(result: TradeDecisionResult) -> dict[str, object]:
        payload: dict[str, object] = {
            "features": asdict(result.features),
            "signal": asdict(result.signal),
            "regime": asdict(result.regime),
            "sizing": asdict(result.sizing),
        }
        if result.transition_state is not None:
            from dataclasses import asdict as _asdict  # local import to avoid circular
            payload["transition_state"] = _asdict(result.transition_state)
        return payload
