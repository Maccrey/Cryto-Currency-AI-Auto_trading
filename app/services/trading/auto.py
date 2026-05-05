from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.market.upbit_ticker import UpbitTickerSnapshot
from app.services.portfolio.sync import PortfolioState
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService
from app.services.position.exit import PositionExitService


@dataclass(frozen=True)
class AutoTradingConfig:
    enabled: bool
    live_enabled: bool
    interval_sec: float
    min_history: int
    trading_profile: str = "scalping"
    spread_bps: float = 8.0
    slippage_bps: float = 12.0
    trading_fee_rate: float = 0.0005
    no_trade_adaptive_enabled: bool = True
    no_trade_relax_after_cycles: int = 100
    no_trade_relax_min_score: float = 0.30


class AutoTradingService:
    """Run a conservative autonomous trading loop and record every decision path."""

    def __init__(
        self,
        *,
        market: str,
        trading_mode: str,
        boot_state: BootState,
        price_provider: Any,
        market_price_store: MarketPriceStore,
        position_store: CurrentPositionStore,
        trade_decision_service: TradeDecisionService,
        trade_execution_service: TradeExecutionService,
        post_fill_service: PostFillService,
        position_exit_service: PositionExitService,
        learning_service: LearningService,
        config: AutoTradingConfig,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Any] | None = None,
        external_context_provider: Any | None = None,
    ) -> None:
        self._market = market
        self._trading_mode = trading_mode
        self._boot_state = boot_state
        self._price_provider = price_provider
        self._market_price_store = market_price_store
        self._position_store = position_store
        self._trade_decision_service = trade_decision_service
        self._trade_execution_service = trade_execution_service
        self._post_fill_service = post_fill_service
        self._position_exit_service = position_exit_service
        self._learning_service = learning_service
        self._config = config
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._sleep = sleep or asyncio.sleep
        self._external_context_provider = external_context_provider
        self._prices: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._traded_values: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._position_opened_at: datetime | None = None
        self._task: asyncio.Task[None] | None = None
        portfolio = getattr(boot_state, "portfolio_state", None)
        self._demo_cash_balance = 0.0 if portfolio is None else portfolio.cash_balance
        self._demo_asset_currency = self._market.split("-")[-1] if portfolio is None else portfolio.asset_currency
        self._demo_asset_balance = 0.0 if portfolio is None else portfolio.asset_balance
        self._demo_avg_buy_price = 0.0 if portfolio is None else portfolio.avg_buy_price
        self._consecutive_entry_blocks = 0

    def should_run(self) -> bool:
        if not self._config.enabled:
            return False
        if self._trading_mode == "live" and not self._config.live_enabled:
            return False
        return self._boot_state.trading_ready and not self._boot_state.hard_stop

    def start(self) -> None:
        if not self.should_run():
            self._record_cycle(status="disabled", reason="AUTO_TRADING_DISABLED_OR_NOT_READY")
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def reset_demo_portfolio(self) -> dict[str, object]:
        if self._trading_mode != "demo":
            return {
                "reset": False,
                "message": "demo trading data reset is only available in demo mode",
            }
        portfolio = getattr(self._boot_state, "portfolio_state", None)
        self._demo_cash_balance = 0.0 if portfolio is None else portfolio.cash_balance
        self._demo_asset_currency = self._market.split("-")[-1] if portfolio is None else portfolio.asset_currency
        self._demo_asset_balance = 0.0 if portfolio is None else portfolio.asset_balance
        self._demo_avg_buy_price = 0.0 if portfolio is None else portfolio.avg_buy_price
        self._position_opened_at = None
        return {
            "reset": True,
            "cash_balance": round(self._demo_cash_balance, 2),
            "asset_currency": self._demo_asset_currency,
            "asset_balance": round(self._demo_asset_balance, 8),
        }

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.to_thread(self.tick)
            await self._sleep(self._config.interval_sec)

    def tick(self) -> dict[str, object]:
        if not self.should_run():
            return self._record_cycle(status="disabled", reason="AUTO_TRADING_DISABLED_OR_NOT_READY")

        try:
            snapshot = self._get_snapshot()
        except Exception as exc:
            return self._record_cycle(status="waiting", reason="PRICE_PROVIDER_ERROR", extra={"error": str(exc)})
        if snapshot is None:
            return self._record_cycle(status="waiting", reason="PRICE_SNAPSHOT_UNAVAILABLE")
        if snapshot.trade_price <= 0:
            return self._record_cycle(status="waiting", reason="INVALID_PRICE_SNAPSHOT")

        self._market_price_store.save(market=self._market, price=snapshot.trade_price)
        self._prices.append(snapshot.trade_price)
        self._traded_values.append(self._traded_value(snapshot))

        position = self._position_store.get()
        if position is not None:
            result = self._position_exit_service.evaluate_and_execute(
                current_price=snapshot.trade_price,
                elapsed_sec=self._elapsed_sec(),
                momentum_score=self._momentum_score(),
                orderbook_imbalance=self._orderbook_imbalance(),
            )
            if result.get("position") is None:
                self._position_opened_at = None
            self._apply_demo_execution(result.get("execution"))
            return self._record_cycle(
                status="position_checked",
                reason=None if result.get("trigger") is None else "POSITION_EXIT_TRIGGERED",
                extra={"position_result": result},
            )

        portfolio = self._portfolio_state()
        if self._trading_mode == "demo" and portfolio.asset_balance > 0:
            return self._record_cycle(
                status="blocked",
                reason="DEMO_ASSET_WITHOUT_ACTIVE_POSITION",
                extra={
                    "cash_balance": portfolio.cash_balance,
                    "asset_balance": portfolio.asset_balance,
                    "avg_buy_price": portfolio.avg_buy_price,
                },
            )

        if len(self._prices) < self._config.min_history:
            return self._record_cycle(
                status="waiting",
                reason="MARKET_HISTORY_WARMING_UP",
                extra={"history_count": len(self._prices), "required_history": self._config.min_history},
            )

        request = self._build_decision_request(snapshot.trade_price)
        decision = self._trade_decision_service.evaluate(request)
        relaxed_signal = self._should_relax_weak_signal(decision)
        if decision.signal.level == "weak" and not relaxed_signal:
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason="AUTO_MIN_SIGNAL_LEVEL",
                extra={
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                },
            )
        if self._trading_mode == "demo" and not self._can_afford_demo_buy(decision.sizing.buy_amount):
            return self._record_cycle(
                status="blocked",
                reason="DEMO_CASH_LIMIT",
                extra={
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "sizing_allowed": decision.sizing.allowed,
                    "buy_amount": decision.sizing.buy_amount,
                    "cash_balance": self._portfolio_state().cash_balance,
                },
            )
        execution_result = self._trade_execution_service.execute(decision)
        post_fill_result = self._post_fill_service.process(execution_result)
        self._apply_demo_execution(execution_result.execution)
        if post_fill_result.position is not None:
            self._position_opened_at = self._clock()
            self._consecutive_entry_blocks = 0

        return self._record_cycle(
            status=execution_result.status,
            reason=execution_result.blocked_reason,
            extra={
                "signal_level": decision.signal.level,
                "signal_score": decision.signal.score,
                "signal_blocked": decision.signal.blocked,
                "signal_reason_codes": decision.signal.reason_codes,
                "sizing_allowed": decision.sizing.allowed,
                "sizing_blocked_reason": decision.sizing.blocked_reason,
                "buy_amount": decision.sizing.buy_amount,
                "no_trade_relaxed": relaxed_signal,
                "post_fill_position_opened": post_fill_result.position is not None,
            },
        )

    def _get_snapshot(self) -> UpbitTickerSnapshot | None:
        get_current_snapshot = getattr(self._price_provider, "get_current_snapshot", None)
        if get_current_snapshot is not None:
            return get_current_snapshot(self._market)
        price = self._price_provider.get_current_price(self._market)
        if price is None:
            return None
        return UpbitTickerSnapshot(trade_price=float(price))

    def _build_decision_request(self, current_price: float) -> TradeDecisionRequest:
        return TradeDecisionRequest(
            prices=list(self._prices),
            traded_values=list(self._traded_values),
            spread_bps=self._config.spread_bps,
            orderbook_imbalance=self._orderbook_imbalance(),
            liquidity_score=self._liquidity_score(),
            regime_score=self._regime_score(),
            current_price=current_price,
            slippage_bps=self._config.slippage_bps,
            portfolio=self._portfolio_state(),
            safe_mode=self._boot_state.safe_mode,
            recent_loss_streak=0,
        )

    def _portfolio_state(self) -> PortfolioState:
        if self._trading_mode == "demo":
            return PortfolioState(
                cash_balance=max(round(self._demo_cash_balance, 2), 0.0),
                asset_currency=self._demo_asset_currency,
                asset_balance=max(round(self._demo_asset_balance, 8), 0.0),
                avg_buy_price=round(self._demo_avg_buy_price, 8),
            )
        if self._boot_state.portfolio_state is not None:
            return self._boot_state.portfolio_state
        return PortfolioState(
            cash_balance=0.0,
            asset_currency=self._market.split("-")[-1],
            asset_balance=0.0,
            avg_buy_price=0.0,
        )

    def _apply_demo_execution(self, execution) -> None:
        if self._trading_mode != "demo" or execution is None:
            return
        if isinstance(execution, dict):
            status = execution.get("status")
            side = execution.get("side")
            price = float(execution.get("filled_price", 0.0) or 0.0)
            quantity = float(execution.get("filled_quantity", 0.0) or 0.0)
            fee = float(execution.get("fee", 0.0) or 0.0)
        else:
            status = getattr(execution, "status", None)
            side = getattr(execution, "side", None)
            price = float(getattr(execution, "filled_price", 0.0) or 0.0)
            quantity = float(getattr(execution, "filled_quantity", 0.0) or 0.0)
            fee = float(getattr(execution, "fee", 0.0) or 0.0)
        if status != "filled" or price <= 0 or quantity <= 0:
            return
        gross_amount = price * quantity
        if side == "buy":
            if gross_amount + fee > self._demo_cash_balance:
                return
            total_cost = (self._demo_avg_buy_price * self._demo_asset_balance) + gross_amount + fee
            self._demo_asset_balance += quantity
            self._demo_cash_balance -= gross_amount + fee
            self._demo_avg_buy_price = 0.0 if self._demo_asset_balance <= 0 else total_cost / self._demo_asset_balance
            return
        if side == "sell":
            sell_quantity = min(self._demo_asset_balance, quantity)
            self._demo_cash_balance += (price * sell_quantity) - fee
            self._demo_asset_balance = round(self._demo_asset_balance - sell_quantity, 8)
            if self._demo_asset_balance <= 0:
                self._demo_asset_balance = 0.0
                self._demo_avg_buy_price = 0.0

    def _can_afford_demo_buy(self, buy_amount: float) -> bool:
        if buy_amount <= 0:
            return False
        estimated_total_cost = buy_amount * (1 + self._config.trading_fee_rate)
        return estimated_total_cost <= self._demo_cash_balance + 1e-6

    def _traded_value(self, snapshot: UpbitTickerSnapshot) -> float:
        value = snapshot.acc_trade_price_24h
        if value is None or value <= 0:
            value = snapshot.trade_price
        return float(value)

    def _orderbook_imbalance(self) -> float:
        if len(self._prices) < 2:
            return 0.0
        previous = self._prices[-2]
        if previous <= 0:
            return 0.0
        return max(min((self._prices[-1] - previous) / previous * 25, 0.5), -0.5)

    def _momentum_score(self) -> float:
        if len(self._prices) < 2 or self._prices[0] <= 0:
            return 0.0
        return max(min((self._prices[-1] - self._prices[0]) / self._prices[0] * 25, 1.0), -1.0)

    def _regime_score(self) -> float:
        return max(min(0.5 + self._momentum_score() * 0.25, 0.85), 0.2)

    def _liquidity_score(self) -> float:
        if len(self._traded_values) < 2:
            return 0.5
        return 0.9 if self._traded_values[-1] >= self._traded_values[-2] else 0.6

    def _elapsed_sec(self) -> int:
        if self._position_opened_at is None:
            return 0
        return max(int((self._clock() - self._position_opened_at).total_seconds()), 0)

    def _record_cycle(
        self,
        *,
        status: str,
        reason: str | None,
        extra: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": status,
            "reason": reason,
            "trading_mode": self._trading_mode,
            "trading_profile": self._config.trading_profile,
            "safe_mode": self._boot_state.safe_mode,
            "hard_stop": self._boot_state.hard_stop,
            "trading_ready": self._boot_state.trading_ready,
        }
        external_context = self._external_context()
        if external_context is not None:
            payload["external_context"] = external_context
        if extra is not None:
            payload.update(extra)
        self._learning_service.record(
            LearningEvent(
                event_name="auto_trade_cycle",
                market=self._market,
                mode=self._trading_mode,
                payload=payload,
            ),
        )
        return payload

    def _external_context(self) -> dict[str, object] | None:
        if self._external_context_provider is None:
            return None
        snapshot = self._external_context_provider.snapshot(
            market=self._market,
            trade_coin=self._market.split("-")[-1],
        )
        self._learning_service.record(
            LearningEvent(
                event_name="external_market_context_snapshot",
                market=self._market,
                mode=self._trading_mode,
                payload=snapshot,
            ),
        )
        return snapshot

    def _should_relax_weak_signal(self, decision) -> bool:
        if not self._config.no_trade_adaptive_enabled:
            return False
        if self._consecutive_entry_blocks < self._config.no_trade_relax_after_cycles:
            return False
        return (
            decision.signal.level == "weak"
            and not decision.signal.blocked
            and decision.signal.score >= self._config.no_trade_relax_min_score
            and decision.sizing.allowed
        )
