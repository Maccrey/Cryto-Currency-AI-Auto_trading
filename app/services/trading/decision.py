from __future__ import annotations

from dataclasses import asdict, dataclass

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
        regime = self._regime_engine.evaluate(
            features,
            recent_loss_streak=request.recent_loss_streak,
            safe_mode=request.safe_mode,
            current_price=request.current_price,
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
    def to_payload(result: TradeDecisionResult) -> dict[str, object]:
        return {
            "features": asdict(result.features),
            "signal": asdict(result.signal),
            "regime": asdict(result.regime),
            "sizing": asdict(result.sizing),
        }
