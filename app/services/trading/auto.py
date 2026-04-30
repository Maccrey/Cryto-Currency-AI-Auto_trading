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
        self._prices: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._traded_values: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._position_opened_at: datetime | None = None
        self._task: asyncio.Task[None] | None = None

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
            return self._record_cycle(
                status="position_checked",
                reason=None if result.get("trigger") is None else "POSITION_EXIT_TRIGGERED",
                extra={"position_result": result},
            )

        if len(self._prices) < self._config.min_history:
            return self._record_cycle(
                status="waiting",
                reason="MARKET_HISTORY_WARMING_UP",
                extra={"history_count": len(self._prices), "required_history": self._config.min_history},
            )

        request = self._build_decision_request(snapshot.trade_price)
        decision = self._trade_decision_service.evaluate(request)
        if decision.signal.level == "weak":
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
        execution_result = self._trade_execution_service.execute(decision)
        post_fill_result = self._post_fill_service.process(execution_result)
        if post_fill_result.position is not None:
            self._position_opened_at = self._clock()

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
        if self._boot_state.portfolio_state is not None:
            return self._boot_state.portfolio_state
        return PortfolioState(
            cash_balance=0.0,
            asset_currency=self._market.split("-")[-1],
            asset_balance=0.0,
            avg_buy_price=0.0,
        )

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
