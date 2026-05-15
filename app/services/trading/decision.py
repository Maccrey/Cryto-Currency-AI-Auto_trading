from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeEngine, RegimeSnapshot
from app.services.signals.engine import SignalDecision, SignalEngine
from app.services.signals.features import FeatureSnapshot, MarketFeatureCalculator
from app.services.sizing.engine import SizingDecision, SizingEngine


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

    @staticmethod
    def _apply_external_context(signal: SignalDecision, weight: float) -> SignalDecision:
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
        return {
            "features": asdict(result.features),
            "signal": asdict(result.signal),
            "regime": asdict(result.regime),
            "sizing": asdict(result.sizing),
        }
