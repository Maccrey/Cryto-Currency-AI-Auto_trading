from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier
from app.services.market.upbit_ticker import UpbitTickerSnapshot
from app.services.portfolio.sync import PortfolioState
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService
from app.services.trading.variants import DemoRuleVariantShadowTester
from app.services.position.exit import PositionExitService
from app.services.risk.market_shock import MarketShockConfig, MarketShockRiskGuard
from app.services.risk.reentry import ReentryBlocker
from app.services.risk.sideways import SidewaysMarketRiskGuard, SidewaysRiskConfig


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
    no_trade_relax_min_score: float = 0.18
    scale_in_enabled: bool = True
    scale_in_max_price_premium_pct: float = 0.0
    reentry_block_seconds: int = 180
    sideways_risk_guard_enabled: bool = True
    sideways_price_range_pct: float = 0.002
    sideways_traded_value_range_pct: float = 0.003
    sideways_max_avg_abs_return_pct: float = 0.001
    sideways_scale_in_min_discount_pct: float = 0.003
    market_shock_guard_enabled: bool = True
    market_crash_change_pct: float = -0.015
    market_surge_change_pct: float = 0.020
    market_recovery_change_pct: float = 0.003
    market_recovery_confirmation_ticks: int = 3
    market_shock_alert_cooldown_sec: int = 300


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
        demo_portfolio_state: PortfolioState | None = None,
        auto_rule_update_service: Any | None = None,
        live_portfolio_sync_service: Any | None = None,
        telegram_notifier: Any | None = None,
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
        self._auto_rule_update_service = auto_rule_update_service
        self._live_portfolio_sync_service = live_portfolio_sync_service
        self._telegram_notifier = telegram_notifier
        self._trend_classifier = MarketTrendClassifier()
        self._prices: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._traded_values: deque[float] = deque(maxlen=max(config.min_history, 2))
        self._position_opened_at: datetime | None = None
        self._started_at: datetime | None = None
        self._task: asyncio.Task[None] | None = None
        portfolio = demo_portfolio_state if trading_mode == "demo" else getattr(boot_state, "portfolio_state", None)
        if portfolio is None:
            portfolio = getattr(boot_state, "portfolio_state", None)
        self._demo_cash_balance = 0.0 if portfolio is None else portfolio.cash_balance
        self._demo_asset_currency = self._market.split("-")[-1] if portfolio is None else portfolio.asset_currency
        self._demo_asset_balance = 0.0 if portfolio is None else portfolio.asset_balance
        self._demo_avg_buy_price = 0.0 if portfolio is None else portfolio.avg_buy_price
        self._consecutive_entry_blocks = 0
        self._reentry_blocker = ReentryBlocker(block_seconds=config.reentry_block_seconds)
        self._sideways_risk_guard = SidewaysMarketRiskGuard(
            SidewaysRiskConfig(
                enabled=config.sideways_risk_guard_enabled,
                price_range_pct=config.sideways_price_range_pct,
                traded_value_range_pct=config.sideways_traded_value_range_pct,
                max_avg_abs_return_pct=config.sideways_max_avg_abs_return_pct,
                scale_in_min_discount_pct=config.sideways_scale_in_min_discount_pct,
            ),
        )
        self._market_shock_guard = MarketShockRiskGuard(
            MarketShockConfig(
                enabled=config.market_shock_guard_enabled,
                crash_change_pct=config.market_crash_change_pct,
                surge_change_pct=config.market_surge_change_pct,
                recovery_change_pct=config.market_recovery_change_pct,
                recovery_confirmation_ticks=config.market_recovery_confirmation_ticks,
            ),
        )
        self._demo_rule_variant_shadow_tester = DemoRuleVariantShadowTester(
            trading_fee_rate=config.trading_fee_rate,
        )
        self._last_cycle: dict[str, object] | None = None
        self._pending_live_order_id: str | None = None
        self._last_market_shock_alert_at: dict[str, int] = {}

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
        self._started_at = self._clock()
        self._task = asyncio.create_task(self._run())

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def started_at(self) -> datetime | None:
        return self._started_at if self.is_running() else None

    def uptime_sec(self) -> int | None:
        started_at = self.started_at()
        if started_at is None:
            return None
        return max(int((self._clock() - started_at).total_seconds()), 0)

    def last_cycle(self) -> dict[str, object] | None:
        return dict(self._last_cycle) if self._last_cycle is not None else None

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
            self._started_at = None

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
        shock_decision = None
        if len(self._prices) >= self._config.min_history:
            shock_decision = self._market_shock_guard.check(prices=list(self._prices))
            self._notify_market_shock_if_needed(
                shock_type=shock_decision.alert_type,
                recent_change_pct=shock_decision.recent_change_pct,
                current_price=snapshot.trade_price,
            )

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
            if result.get("trigger") is not None:
                trigger = result.get("trigger")
                if isinstance(trigger, dict):
                    self._reentry_blocker.record_exit(
                        market=self._market,
                        side="sell",
                        reason_code=None if trigger.get("reason_code") is None else str(trigger.get("reason_code")),
                        triggered_at=int(self._clock().timestamp()),
                        price=snapshot.trade_price,
                    )
                return self._record_cycle(
                    status="position_checked",
                    reason="POSITION_EXIT_TRIGGERED",
                    extra={"position_result": result},
                )
            if not self._scale_in_allowed(position=position, current_price=snapshot.trade_price):
                return self._record_cycle(
                    status="position_checked",
                    reason="POSITION_HELD",
                    extra={"position_result": result},
                )

        if self._pending_live_order_id is not None:
            pending_result = self._resolve_pending_live_order()
            if not pending_result["resolved"]:
                return self._record_cycle(
                    status="blocked",
                    reason="LIVE_ORDER_PENDING",
                    extra=pending_result,
                )

        portfolio = self._portfolio_state()
        if self._trading_mode == "demo" and portfolio.asset_balance > 0 and position is None:
            return self._record_cycle(
                status="blocked",
                reason="DEMO_ASSET_WITHOUT_ACTIVE_POSITION",
                extra={
                    "cash_balance": portfolio.cash_balance,
                    "asset_balance": portfolio.asset_balance,
                    "avg_buy_price": portfolio.avg_buy_price,
                },
            )
        if self._trading_mode == "live" and portfolio.asset_balance > 0 and position is None:
            return self._record_cycle(
                status="blocked",
                reason="LIVE_ASSET_WITHOUT_ACTIVE_POSITION",
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

        if shock_decision is None:
            shock_decision = self._market_shock_guard.check(prices=list(self._prices))
        if not shock_decision.allowed:
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=shock_decision.reason_code,
                extra={
                    "buy_amount": 0.0,
                    "market_shock_state": shock_decision.shock_state,
                    "market_shock_recent_change_pct": shock_decision.recent_change_pct,
                    "market_shock_last_return_pct": shock_decision.last_return_pct,
                    "market_shock_recovery_count": shock_decision.recovery_count,
                    "market_shock_required_recovery_count": self._config.market_recovery_confirmation_ticks,
                },
            )

        request = self._build_decision_request(snapshot.trade_price)
        decision = self._trade_decision_service.evaluate(request)
        variant_payload = self._run_demo_rule_variant_shadow(decision=decision, current_price=snapshot.trade_price)
        reentry_decision = self._reentry_blocker.check(
            market=self._market,
            now=int(self._clock().timestamp()),
            current_price=snapshot.trade_price,
        )
        if not reentry_decision.allowed:
            return self._record_cycle(
                status="blocked",
                reason=reentry_decision.reason_code,
                extra={
                    "remaining_seconds": reentry_decision.remaining_seconds,
                    "last_exit_reason_code": reentry_decision.last_exit_reason_code,
                    "last_exit_price": reentry_decision.last_exit_price,
                    "market_state": decision.regime.market_state,
                    "market_state_label": decision.regime.market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                },
            )
        relaxed_signal = self._should_relax_weak_signal(decision)
        sideways_decision = self._sideways_risk_guard.check(
            prices=list(self._prices),
            traded_values=list(self._traded_values),
            current_price=snapshot.trade_price,
            signal_level=decision.signal.level,
            relaxed_signal=relaxed_signal,
            position_entry_price=None if position is None else position.entry_price,
        )
        if not sideways_decision.allowed:
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=sideways_decision.reason_code,
                extra={
                    "entry_type": "scale_in" if position is not None else "initial",
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "market_state": decision.regime.market_state,
                    "market_state_label": decision.regime.market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    "sideways_is_sideways": sideways_decision.is_sideways,
                    "sideways_price_range_pct": sideways_decision.price_range_pct,
                    "sideways_traded_value_range_pct": sideways_decision.traded_value_range_pct,
                    "sideways_avg_abs_return_pct": sideways_decision.avg_abs_return_pct,
                    "sideways_min_scale_in_price": sideways_decision.min_scale_in_price,
                    "no_trade_relaxed": relaxed_signal,
                    **rule_variant,
                },
            )
        if relaxed_signal and decision.sizing.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT":
            decision = self._trade_decision_service.evaluate(
                self._build_decision_request(snapshot.trade_price, relax_fee_edge=True),
            )
            variant_payload = self._run_demo_rule_variant_shadow(decision=decision, current_price=snapshot.trade_price)
        if decision.signal.level == "weak" and not relaxed_signal:
            self._consecutive_entry_blocks += 1
            rule_variant = self._variant_extra(variant_payload)
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
                "market_state": decision.regime.market_state,
                "market_state_label": decision.regime.market_state_label,
                "box_range_low": decision.regime.box_range_low,
                "box_range_high": decision.regime.box_range_high,
                **rule_variant,
            },
        )
        if self._trading_mode == "demo" and not self._can_afford_demo_buy(decision.sizing.buy_amount):
            rule_variant = self._variant_extra(variant_payload)
            return self._record_cycle(
                status="blocked",
                reason="DEMO_CASH_LIMIT",
                extra={
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "sizing_allowed": decision.sizing.allowed,
                "buy_amount": decision.sizing.buy_amount,
                "market_state": decision.regime.market_state,
                "market_state_label": decision.regime.market_state_label,
                "box_range_low": decision.regime.box_range_low,
                "box_range_high": decision.regime.box_range_high,
                "cash_balance": self._portfolio_state().cash_balance,
                **rule_variant,
            },
        )
        execution_result = self._trade_execution_service.execute(decision)
        post_fill_result = self._post_fill_service.process(execution_result)
        self._apply_demo_execution(execution_result.execution)
        self._record_pending_live_order(execution_result.execution)
        if post_fill_result.position is not None:
            self._position_opened_at = self._clock()
            self._consecutive_entry_blocks = 0

        return self._record_cycle(
            status=execution_result.status,
            reason=execution_result.blocked_reason,
            extra={
                "entry_type": "scale_in" if position is not None else "initial",
                "signal_level": decision.signal.level,
                "signal_score": decision.signal.score,
                "signal_blocked": decision.signal.blocked,
                "signal_reason_codes": decision.signal.reason_codes,
                "sizing_allowed": decision.sizing.allowed,
                "sizing_blocked_reason": decision.sizing.blocked_reason,
                "buy_amount": decision.sizing.buy_amount,
                "sell_ratio": decision.sizing.sell_ratio,
                "sell_quantity": decision.sizing.sell_quantity,
                "market_state": decision.regime.market_state,
                "market_state_label": decision.regime.market_state_label,
                "box_range_low": decision.regime.box_range_low,
                "box_range_high": decision.regime.box_range_high,
                "no_trade_relaxed": relaxed_signal,
                "post_fill_position_opened": post_fill_result.position is not None,
                **self._variant_extra(variant_payload),
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

    def _build_decision_request(self, current_price: float, *, relax_fee_edge: bool = False) -> TradeDecisionRequest:
        external_context = self._external_context(record=False)
        trend = self._trend_classifier.classify(
            current_price=current_price,
            history=self._market_price_store.list_history(self._market),
            learning_events=self._learning_service.recent_events(limit=200),
        )
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
            relax_fee_edge=relax_fee_edge,
            external_context_weight=self._external_context_weight(external_context),
            observed_market_state=trend.market_state,
            observed_market_state_label=trend.market_state_label,
            observed_box_range_low=trend.box_range_low,
            observed_box_range_high=trend.box_range_high,
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

    def _record_pending_live_order(self, execution) -> None:
        if self._trading_mode != "live" or execution is None:
            return
        if getattr(execution, "accepted", False):
            self._pending_live_order_id = getattr(execution, "order_id", None) or "unknown"

    def _notify_market_shock_if_needed(
        self,
        *,
        shock_type: str | None,
        recent_change_pct: float,
        current_price: float,
    ) -> None:
        if shock_type is None or self._telegram_notifier is None:
            return
        now = int(self._clock().timestamp())
        last_alert_at = self._last_market_shock_alert_at.get(shock_type)
        if last_alert_at is not None and now - last_alert_at < self._config.market_shock_alert_cooldown_sec:
            return
        notify_market_shock = getattr(self._telegram_notifier, "notify_market_shock", None)
        if notify_market_shock is None:
            return
        notify_market_shock(
            market=self._market,
            shock_type=shock_type,
            recent_change_pct=recent_change_pct,
            current_price=current_price,
            mode=self._trading_mode,
        )
        self._last_market_shock_alert_at[shock_type] = now

    def _resolve_pending_live_order(self) -> dict[str, object]:
        order_id = self._pending_live_order_id
        if order_id is None:
            return {"resolved": True}
        try:
            status = self._trade_execution_service.order_status(order_id)
        except Exception as exc:
            return {
                "resolved": False,
                "pending_live_order_id": order_id,
                "order_status_error": str(exc),
            }
        state = str(status.get("state", "unknown"))
        if state not in {"done", "cancel"}:
            return {
                "resolved": False,
                "pending_live_order_id": order_id,
                "live_order_status": status,
            }
        self._pending_live_order_id = None
        sync_payload = self._sync_live_portfolio_after_order()
        return {
            "resolved": True,
            "resolved_live_order_id": order_id,
            "live_order_status": status,
            "portfolio_sync": sync_payload,
        }

    def _sync_live_portfolio_after_order(self) -> dict[str, object]:
        if self._live_portfolio_sync_service is None:
            return {"status": "skipped", "reason": "live_portfolio_sync_unavailable"}
        try:
            portfolio = self._live_portfolio_sync_service.sync()
        except Exception as exc:
            return {"status": "failed", "reason": str(exc)}
        self._boot_state = replace(self._boot_state, portfolio_state=portfolio)
        return {
            "status": "synced",
            "cash_balance": portfolio.cash_balance,
            "asset_currency": portfolio.asset_currency,
            "asset_balance": portfolio.asset_balance,
            "avg_buy_price": portfolio.avg_buy_price,
        }

    def _can_afford_demo_buy(self, buy_amount: float) -> bool:
        if buy_amount <= 0:
            return False
        estimated_total_cost = buy_amount * (1 + self._config.trading_fee_rate)
        return estimated_total_cost <= self._demo_cash_balance + 1e-6

    def _run_demo_rule_variant_shadow(self, *, decision, current_price: float) -> dict[str, object] | None:
        if self._trading_mode != "demo":
            return None
        return self._demo_rule_variant_shadow_tester.evaluate(
            decision=decision,
            current_price=current_price,
            portfolio=self._portfolio_state(),
        )

    @staticmethod
    def _variant_extra(variant_payload: dict[str, object] | None) -> dict[str, object]:
        if variant_payload is None:
            return {}
        return {
            "rule_variant_shadow": variant_payload,
            "rule_variant_leader_key": variant_payload.get("leader_key"),
            "rule_variant_leader_label": variant_payload.get("leader_label"),
            "rule_variant_leader_reason": variant_payload.get("leader_reason"),
        }

    def _scale_in_allowed(self, *, position, current_price: float) -> bool:
        if not self._config.scale_in_enabled:
            return False
        if current_price <= 0 or position.entry_price <= 0:
            return False
        max_price = position.entry_price * (1 + self._config.scale_in_max_price_premium_pct)
        return current_price <= max_price

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
            "learning_completion_rate": self._learning_completion_rate(),
        }
        external_context = self._external_context()
        if external_context is not None:
            payload["external_context"] = external_context
        if extra is not None:
            payload.update(extra)
        self._last_cycle = dict(payload)
        self._learning_service.record(
            LearningEvent(
                event_name="auto_trade_cycle",
                market=self._market,
                mode=self._trading_mode,
                payload=payload,
            ),
        )
        if self._auto_rule_update_service is not None:
            update_result = self._auto_rule_update_service.maybe_run()
            if update_result.get("status") in {"completed", "needs_retry", "failed", "blocked"}:
                self._learning_service.record(
                    LearningEvent(
                        event_name="auto_rule_update",
                        market=self._market,
                        mode=self._trading_mode,
                        payload=update_result,
                    ),
                )
        return payload

    def _external_context(self, *, record: bool = True) -> dict[str, object] | None:
        if self._external_context_provider is None:
            return None
        snapshot = self._external_context_provider.snapshot(
            market=self._market,
            trade_coin=self._market.split("-")[-1],
        )
        if not record:
            return snapshot
        self._learning_service.record(
            LearningEvent(
                event_name="external_market_context_snapshot",
                market=self._market,
                mode=self._trading_mode,
                payload=snapshot,
            ),
        )
        return snapshot

    @staticmethod
    def _external_context_weight(external_context: dict[str, object] | None) -> float:
        if not isinstance(external_context, dict):
            return 1.0
        try:
            return max(min(float(external_context.get("learning_weight", 1.0)), 1.25), 0.75)
        except (TypeError, ValueError):
            return 1.0

    def _should_relax_weak_signal(self, decision) -> bool:
        if self._trading_mode != "demo":
            return False
        if not self._config.no_trade_adaptive_enabled:
            return False
        if self._consecutive_entry_blocks < self._config.no_trade_relax_after_cycles:
            return False
        return (
            decision.signal.level == "weak"
            and not decision.signal.blocked
            and decision.signal.score >= self._config.no_trade_relax_min_score
            and (
                decision.sizing.allowed
                or decision.sizing.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT"
            )
        )

    def _learning_completion_rate(self) -> float:
        if self._config.min_history <= 0:
            return 1.0
        return round(min(len(self._prices) / self._config.min_history, 1.0), 3)
