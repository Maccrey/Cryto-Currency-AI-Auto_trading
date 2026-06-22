from __future__ import annotations

from dataclasses import dataclass

from app.services.replay.loader import ReplayTick
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator


@dataclass(frozen=True)
class ReplayResult:
    timestamp: str
    signal_level: str
    signal_score: float
    blocked: bool
    price: float = 0.0
    action: str = "hold"
    equity: float = 0.0
    profit_rate: float = 0.0


@dataclass(frozen=True)
class ReplaySummary:
    signal_count: int
    blocked_count: int
    trade_count: int
    final_equity: float
    final_profit_rate: float
    max_drawdown_pct: float
    max_signal_score: float
    profit_guard_status: str


class ReplayHarness:
    """Replay historical ticks through feature and signal services."""

    def __init__(
        self,
        *,
        initial_cash: float = 1_000_000.0,
        trading_fee_rate: float = 0.0005,
    ) -> None:
        self._feature_calculator = MarketFeatureCalculator()
        self._signal_engine = SignalEngine()
        self._initial_cash = initial_cash
        self._trading_fee_rate = max(float(trading_fee_rate), 0.0)

    def run(self, ticks: list[ReplayTick]) -> list[ReplayResult]:
        results: list[ReplayResult] = []
        prices: list[float] = []
        traded_values: list[float] = []
        cash = self._initial_cash
        quantity = 0.0

        for tick in ticks:
            prices.append(tick.price)
            traded_values.append(tick.traded_value)
            if len(prices) < 3:
                continue

            features = self._feature_calculator.calculate(
                prices=prices[-4:],
                traded_values=traded_values[-4:],
                spread_bps=tick.spread_bps,
                orderbook_imbalance=tick.orderbook_imbalance,
                liquidity_score=tick.liquidity_score,
                regime_score=tick.regime_score,
            )
            decision = self._signal_engine.evaluate(features)
            action = "hold"
            if not decision.blocked and decision.score >= 0.4 and cash > 0:
                available_notional = cash / (1 + self._trading_fee_rate)
                buy_amount = available_notional * min(max(decision.score, 0.0), 1.0) * 0.2
                if buy_amount > 0 and tick.price > 0:
                    buy_fee = buy_amount * self._trading_fee_rate
                    quantity += buy_amount / tick.price
                    cash -= buy_amount + buy_fee
                    action = "buy"
            elif (decision.blocked or decision.score < 0.25) and quantity > 0 and tick.price > 0:
                sell_notional = quantity * tick.price
                cash += sell_notional - (sell_notional * self._trading_fee_rate)
                quantity = 0.0
                action = "sell"
            liquidation_value = quantity * tick.price * (1 - self._trading_fee_rate)
            equity = cash + liquidation_value
            results.append(
                ReplayResult(
                    timestamp=tick.timestamp,
                    signal_level=decision.level,
                    signal_score=decision.score,
                    blocked=decision.blocked,
                    price=tick.price,
                    action=action,
                    equity=round(equity, 2),
                    profit_rate=round((equity - self._initial_cash) / self._initial_cash, 6),
                ),
            )

        return results

    @staticmethod
    def summarize(results: list[ReplayResult], *, initial_cash: float = 1_000_000.0) -> ReplaySummary:
        if not results:
            return ReplaySummary(
                signal_count=0,
                blocked_count=0,
                trade_count=0,
                final_equity=initial_cash,
                final_profit_rate=0.0,
                max_drawdown_pct=0.0,
                max_signal_score=0.0,
                profit_guard_status="failed",
            )
        peak = initial_cash
        max_drawdown = 0.0
        for result in results:
            peak = max(peak, result.equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - result.equity) / peak)
        final_equity = results[-1].equity
        final_profit_rate = round((final_equity - initial_cash) / initial_cash, 6)
        return ReplaySummary(
            signal_count=len(results),
            blocked_count=sum(1 for result in results if result.blocked),
            trade_count=sum(1 for result in results if result.action in {"buy", "sell"}),
            final_equity=round(final_equity, 2),
            final_profit_rate=final_profit_rate,
            max_drawdown_pct=round(max_drawdown, 6),
            max_signal_score=max((result.signal_score for result in results), default=0.0),
            profit_guard_status=(
                "passed"
                if final_profit_rate > 0.0
                and sum(1 for result in results if result.action in {"buy", "sell"}) > 0
                and max_drawdown <= 0.02
                else "failed"
            ),
        )
