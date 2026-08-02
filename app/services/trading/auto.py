from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier
from app.services.market.upbit_ticker import UpbitTickerSnapshot
from app.services.execution.ledger import ExecutionLedger, ExecutionPerformanceProfile
from app.services.portfolio.sync import PortfolioState
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState
from app.services.trading.decision import TradeDecisionRequest, TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.market_state import MarketStateEntryGuard
from app.services.trading.post_fill import PostFillService
from app.services.trading.variants import DemoRuleVariantShadowTester
from app.services.position.exit import PositionExitService
from app.services.risk.market_shock import MarketShockConfig, MarketShockRiskGuard
from app.services.risk.reentry import AdaptiveCooldownReentryPolicy, ReentryBlocker
from app.services.risk.sideways import SidewaysMarketRiskGuard, SidewaysRiskConfig
from app.services.runtime.uptime import TradingUptimeStore


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
    max_daily_loss: float = 150_000.0
    no_trade_adaptive_enabled: bool = True
    no_trade_relax_after_cycles: int = 100
    no_trade_relax_min_score: float = 0.18
    allow_weak_no_trade_relax: bool = False
    scale_in_enabled: bool = True
    scale_in_max_price_premium_pct: float = 0.0
    scale_in_max_entries: int = 2
    scale_in_max_position_multiplier: float = 0.55
    bull_scale_in_enabled: bool = True
    bull_scale_in_max_price_premium_pct: float = 0.004
    bull_scale_in_min_traded_value_multiple: float = 1.03
    # Legacy single cooldown kept for backward compatibility.
    # When non-zero the adaptive policy below is ignored.
    reentry_block_seconds: int = 0
    # Adaptive reentry cooldowns: shorter after profit, longer after loss.
    reentry_block_seconds_profit: int = 60
    reentry_block_seconds_loss: int = 120
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
    market_state_entry_guard_enabled: bool = True
    market_state_transition_confirmation_ticks: int = 2
    market_state_bear_entry_min_score: float = 0.65
    historical_loss_guard_enabled: bool = True
    historical_loss_guard_min_fills: int = 20
    historical_loss_guard_min_learning_stop_losses: int = 2
    historical_loss_guard_stop_loss_to_profit_ratio: float = 1.2
    historical_loss_guard_weak_buy_ratio: float = 0.7
    historical_loss_guard_box_entry_min_score: float = 0.30
    initial_observation_warmup_seconds: int = 180
    initial_observation_min_samples: int = 20
    post_stop_loss_max_block_hours: float = 8.0  # 손절 후 재진입 최대 차단 시간(시간). 12→8시간: 더 빠른 재진입 허용.
    rule_update_state_path: Path | None = None


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
        uptime_store: TradingUptimeStore | None = None,
        execution_ledger: ExecutionLedger | None = None,
        etf_context_change_monitor: Any | None = None,
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
        self._rule_update_state_path = config.rule_update_state_path
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._sleep = sleep or asyncio.sleep
        self._external_context_provider = external_context_provider
        self._auto_rule_update_service = auto_rule_update_service
        self._live_portfolio_sync_service = live_portfolio_sync_service
        self._telegram_notifier = telegram_notifier
        self._uptime_store = uptime_store
        self._execution_ledger = execution_ledger
        self._etf_context_change_monitor = etf_context_change_monitor
        self._trend_classifier = MarketTrendClassifier()
        history_size = max(config.min_history, config.initial_observation_min_samples, 2)
        self._prices: deque[float] = deque(maxlen=history_size)
        self._traded_values: deque[float] = deque(maxlen=history_size)
        self._initial_market_history_count = len(market_price_store.list_history(market))
        self._requires_initial_observation_warmup = self._initial_market_history_count <= 0
        self._first_observation_at: datetime | None = None
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
        self._reentry_blocker = ReentryBlocker(
            cooldown_policy=(
                AdaptiveCooldownReentryPolicy(
                    profit_block_seconds=config.reentry_block_seconds_profit,
                    loss_block_seconds=config.reentry_block_seconds_loss,
                )
                if config.reentry_block_seconds == 0
                else None
            ),
            block_seconds=config.reentry_block_seconds if config.reentry_block_seconds > 0 else None,
        ) if config.reentry_block_seconds > 0 else ReentryBlocker(
            cooldown_policy=AdaptiveCooldownReentryPolicy(
                profit_block_seconds=config.reentry_block_seconds_profit,
                loss_block_seconds=config.reentry_block_seconds_loss,
            ),
        )
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
        self._market_state_entry_guard = MarketStateEntryGuard(
            enabled=config.market_state_entry_guard_enabled,
            confirmation_ticks=config.market_state_transition_confirmation_ticks,
            bear_entry_min_score=config.market_state_bear_entry_min_score,
        )
        self._demo_rule_variant_shadow_tester = DemoRuleVariantShadowTester(
            trading_fee_rate=config.trading_fee_rate,
        )
        self._last_cycle: dict[str, object] | None = None
        self._pending_live_order_id: str | None = None
        self._last_ticker_reference_change_pct: float | None = None
        self._last_auto_rule_update_check_at = 0
        self._auto_rule_update_check_interval_sec = 60
        self._last_market_shock_alert_at: dict[str, int] = {}
        self._last_entry_signal_level: str | None = None
        self._last_entry_signal_score: float | None = None
        self._scale_in_count = 0
        # ── 24시간 무거래 시 섀도 포트폴리오 자동 리셋 ────────────────────────────
        # 시작 시각을 기준으로 초기화 (재시작 직후 즉시 리셋 방지)
        _init_now = self._clock()
        self._last_trade_filled_at: datetime = _init_now   # 마지막 매수 체결 시각
        self._last_variant_reset_at: datetime = _init_now  # 마지막 섀도 리셋 시각
        self._restore_verified_rule_updates()

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
        self._started_at = self._clock() if self._uptime_store is None else self._uptime_store.start()
        self._task = asyncio.create_task(self._run())

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def started_at(self) -> datetime | None:
        return self._started_at if self.is_running() else None

    def uptime_sec(self) -> int | None:
        started_at = self.started_at()
        if started_at is None:
            return None
        if self._uptime_store is not None:
            return self._uptime_store.uptime_sec(fallback_started_at=started_at)
        return max(int((self._clock() - started_at).total_seconds()), 0)

    def last_cycle(self) -> dict[str, object] | None:
        return dict(self._last_cycle) if self._last_cycle is not None else None

    def set_demo_portfolio_baseline(self, portfolio: PortfolioState) -> dict[str, object]:
        if self._trading_mode != "demo":
            return {
                "applied": False,
                "message": "demo portfolio baseline is only available in demo mode",
            }
        try:
            self._boot_state = replace(self._boot_state, portfolio_state=portfolio)
        except TypeError:
            setattr(self._boot_state, "portfolio_state", portfolio)
        self._demo_cash_balance = portfolio.cash_balance
        self._demo_asset_currency = portfolio.asset_currency
        self._demo_asset_balance = portfolio.asset_balance
        self._demo_avg_buy_price = portfolio.avg_buy_price
        return {
            "applied": True,
            "cash_balance": round(self._demo_cash_balance, 2),
            "asset_currency": self._demo_asset_currency,
            "asset_balance": round(self._demo_asset_balance, 8),
        }

    def current_demo_portfolio_state(self) -> PortfolioState | None:
        """현재 데모 포트폴리오 상태를 반환합니다. 데모 모드가 아닌 경우 None 반환."""
        if self._trading_mode != "demo":
            return None
        return PortfolioState(
            cash_balance=self._demo_cash_balance,
            asset_currency=self._demo_asset_currency,
            asset_balance=self._demo_asset_balance,
            avg_buy_price=self._demo_avg_buy_price,
        )

    def reset_runtime_market_data(self) -> dict[str, object]:
        self._prices.clear()
        self._traded_values.clear()
        self._market_price_store.clear(self._market)
        self._initial_market_history_count = 0
        self._requires_initial_observation_warmup = True
        self._first_observation_at = None
        self._last_cycle = None
        self._last_ticker_reference_change_pct = None
        self._consecutive_entry_blocks = 0
        self._last_market_shock_alert_at.clear()
        return {
            "reset": True,
            "market": self._market,
            "price_history_count": 0,
        }

    def reset_demo_rule_variants(self) -> None:
        self._demo_rule_variant_shadow_tester.reset()

    def apply_demo_rule_update(self, changes: list[dict[str, Any]]) -> dict[str, object]:
        """Persist a verified demo rule so the matching live profile uses it too."""
        if self._trading_mode != "demo":
            return {"applied": False, "reason": "demo_mode_required", "parameters": []}
        result = self._apply_verified_rule_updates(changes)
        if result["applied"]:
            self._persist_verified_rule_updates(changes)
        return result

    def _apply_verified_rule_updates(self, changes: list[dict[str, Any]]) -> dict[str, object]:
        parameters = {str(change.get("parameter")) for change in changes if isinstance(change, dict)}
        updates: dict[str, object] = {}
        if "NO_TRADE_RELAX_MIN_SCORE" in parameters:
            self._config = replace(self._config, no_trade_relax_min_score=0.18)
            updates["NO_TRADE_RELAX_MIN_SCORE"] = 0.18
        if "BULL_BOX_BEAR_REBOUND_SIGNAL_BOOST" in parameters:
            self._config = replace(self._config, allow_weak_no_trade_relax=True)
            updates["BULL_BOX_BEAR_REBOUND_SIGNAL_BOOST"] = "enabled_after_fee_edge_check"
        decision_overrides: dict[str, float] = {}
        if "TECHNICAL_TREND_CONFIRMATION" in parameters:
            decision_overrides["technical_trend_confirmation_boost"] = 0.03
        if "TECHNICAL_BEARISH_SIZE_REDUCTION" in parameters:
            decision_overrides["bearish_entry_score_multiplier"] = 0.90
        if "EXTERNAL_CONTEXT_BULLISH_BOOST" in parameters:
            decision_overrides["external_context_bullish_multiplier"] = 1.002
        if decision_overrides and hasattr(self._trade_decision_service, "set_demo_rule_overrides"):
            updates.update(self._trade_decision_service.set_demo_rule_overrides(decision_overrides))
        return {"applied": bool(updates), "parameters": updates}

    def _persist_verified_rule_updates(self, changes: list[dict[str, Any]]) -> None:
        if self._rule_update_state_path is None:
            return
        self._rule_update_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._rule_update_state_path.write_text(
            json.dumps({"changes": changes}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def _restore_verified_rule_updates(self) -> None:
        if self._rule_update_state_path is None or not self._rule_update_state_path.exists():
            return
        try:
            payload = json.loads(self._rule_update_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        changes = payload.get("changes") if isinstance(payload, dict) else None
        if isinstance(changes, list):
            self._apply_verified_rule_updates([change for change in changes if isinstance(change, dict)])

    def reset_demo_portfolio(self, portfolio: PortfolioState | None = None) -> dict[str, object]:
        if self._trading_mode != "demo":
            return {
                "reset": False,
                "message": "demo trading data reset is only available in demo mode",
            }
        if portfolio is not None:
            self.set_demo_portfolio_baseline(portfolio)
        else:
            portfolio = getattr(self._boot_state, "portfolio_state", None)
            if portfolio is None:
                self._demo_cash_balance = 0.0
                self._demo_asset_currency = self._market.split("-")[-1]
                self._demo_asset_balance = 0.0
                self._demo_avg_buy_price = 0.0
            else:
                self.set_demo_portfolio_baseline(portfolio)
        self._position_opened_at = None
        self._last_entry_signal_level = None
        self._last_entry_signal_score = None
        self._scale_in_count = 0
        self.reset_demo_rule_variants()
        if self._uptime_store is not None:
            self._uptime_store.reset()
            if self.is_running():
                self._started_at = self._uptime_store.start()
        return {
            "reset": True,
            "cash_balance": round(self._demo_cash_balance, 2),
            "asset_currency": self._demo_asset_currency,
            "asset_balance": round(self._demo_asset_balance, 8),
            "rule_variant_shadow_reset": True,
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
            if self._uptime_store is not None and self._started_at is not None:
                self._uptime_store.stop()
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

        self._last_ticker_reference_change_pct = snapshot.signed_change_rate
        self._market_price_store.save(market=self._market, price=snapshot.trade_price)
        if self._first_observation_at is None:
            self._first_observation_at = self._clock()
        self._prices.append(snapshot.trade_price)
        self._traded_values.append(self._traded_value(snapshot))
        self._record_market_observation(snapshot)
        shock_decision = None
        if len(self._prices) >= self._config.min_history:
            shock_decision = self._market_shock_guard.check(prices=list(self._prices))
            self._notify_market_shock_if_needed(
                shock_type=shock_decision.alert_type,
                recent_change_pct=shock_decision.recent_change_pct,
                current_price=snapshot.trade_price,
            )

        position = self._position_store.get()
        position_market_trend = self._classify_current_market_state(snapshot.trade_price) if position is not None else None
        if position is not None:
            result = self._position_exit_service.evaluate_and_execute(
                current_price=snapshot.trade_price,
                elapsed_sec=self._elapsed_sec(),
                momentum_score=self._momentum_score(),
                orderbook_imbalance=self._orderbook_imbalance(),
                market_state=None if position_market_trend is None else position_market_trend.market_state,
                box_range_low=None if position_market_trend is None else position_market_trend.box_range_low,
                box_range_high=None if position_market_trend is None else position_market_trend.box_range_high,
            )
            if result.get("position") is None:
                self._position_opened_at = None
                self._scale_in_count = 0
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
                # Stop-losses are evaluated before an entry decision exists in this
                # tick.  Use the position and exit-market context instead of the
                # later ``decision`` local, so recording the diagnostic cannot stop
                # the autonomous loop immediately after a protective exit.
                reason_code_str = str(trigger.get("reason_code") or "") if isinstance(trigger, dict) else ""
                if "STOP_LOSS" in reason_code_str:
                    self._learning_service.record(
                        LearningEvent(
                            event_name="stop_loss_triggered",
                            market=self._market,
                            mode=self._trading_mode,
                            payload={
                                "reason_code": reason_code_str,
                                "exit_price": snapshot.trade_price,
                                "trigger": trigger,
                                "market_state": (
                                    None
                                    if position_market_trend is None
                                    else str(position_market_trend.market_state)
                                ),
                                "signal_level": position.signal_level,
                                "signal_score": self._last_entry_signal_score,
                                "position_result": result,
                            },
                        )
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

        daily_loss_guard = self._daily_loss_guard_decision()
        if not daily_loss_guard["allowed"]:
            return self._record_cycle(
                status="blocked",
                reason="DAILY_LOSS_LIMIT",
                extra=daily_loss_guard,
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
        initial_warmup = self._initial_observation_warmup_decision()
        if initial_warmup is not None:
            return self._record_cycle(
                status="waiting",
                reason="INITIAL_MARKET_OBSERVATION_WARMING_UP",
                extra=initial_warmup,
            )

        if shock_decision is None:
            shock_decision = self._market_shock_guard.check(prices=list(self._prices))
        # ── 24시간 무거래 자동 리셋 체크 ───────────────────────────────────────────
        self._check_no_trade_auto_reset(position_exists=position is not None)
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
        available_cash = self._demo_cash_balance if self._trading_mode == "demo" else portfolio.cash_balance
        decision = self._apply_variant_and_gate_entry(
            decision=decision,
            variant_payload=variant_payload,
            current_price=snapshot.trade_price,
            position_exists=position is not None,
            available_cash=available_cash,
        )
        box_range_opportunity = self._box_range_buy_opportunity(
            market_state=decision.regime.market_state,
            box_range_low=decision.regime.box_range_low,
            box_range_high=decision.regime.box_range_high,
            current_price=snapshot.trade_price,
            position_exists=position is not None,
        )
        entry_type = "scale_in" if position is not None else "initial"
        entry_market_state = decision.regime.market_state
        entry_market_state_label = decision.regime.market_state_label
        if self._recent_price_market_state() == "bear":
            entry_market_state = "bear"
            entry_market_state_label = "하락장"
        market_state_entry = self._market_state_entry_guard.evaluate(
            market_state=entry_market_state,
            signal_level=decision.signal.level,
            signal_score=decision.signal.score,
            entry_type=entry_type,
            signal_reason_codes=decision.signal.reason_codes,
        )
        market_state_extra = self._market_state_extra(market_state_entry)
        if not market_state_entry.allowed:
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=market_state_entry.reason_code,
                extra={
                    "entry_type": entry_type,
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "market_state": entry_market_state,
                    "market_state_label": entry_market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    **market_state_extra,
                    **rule_variant,
                },
            )
        log_backed_recovery = self._log_backed_bull_weak_recovery(
            decision=decision,
            variant_payload=variant_payload,
            entry_type=entry_type,
            market_state=entry_market_state,
        )
        historical_loss_guard = self._historical_loss_guard_decision(
            entry_type=entry_type,
            signal_level=decision.signal.level,
            signal_score=decision.signal.score,
            box_range_opportunity=box_range_opportunity,
        )
        trade_logic_update_trace = self._trade_logic_update_trace(
            decision=decision,
            variant_payload=variant_payload,
            entry_type=entry_type,
            market_state=entry_market_state,
            historical_loss_guard=historical_loss_guard,
            log_backed_recovery=log_backed_recovery,
        )
        if not historical_loss_guard["allowed"] and not log_backed_recovery:
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=str(historical_loss_guard["reason_code"]),
                extra={
                    "entry_type": entry_type,
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "market_state": entry_market_state,
                    "market_state_label": entry_market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    **market_state_extra,
                    **self._historical_loss_guard_extra(historical_loss_guard),
                    "trade_logic_update_trace": trade_logic_update_trace,
                    **rule_variant,
                },
            )
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
                    **market_state_extra,
                },
            )
        post_sell_reentry = self._post_sell_reentry_confirmation(
            reentry_decision=reentry_decision,
            decision=decision,
            market_state_entry=market_state_entry,
            current_price=snapshot.trade_price,
            entry_type=entry_type,
        )
        if not post_sell_reentry["allowed"]:
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=str(post_sell_reentry["reason_code"]),
                extra={
                    "entry_type": entry_type,
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "market_state": entry_market_state,
                    "market_state_label": entry_market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    **market_state_extra,
                    **post_sell_reentry,
                    **rule_variant,
                },
            )
        relaxed_signal = (
            market_state_entry.transition_boost
            or log_backed_recovery
            or self._should_relax_weak_signal(decision)
            or bool(box_range_opportunity["allowed"])
        )
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
                    **market_state_extra,
                    "sideways_is_sideways": sideways_decision.is_sideways,
                    "sideways_price_range_pct": sideways_decision.price_range_pct,
                    "sideways_traded_value_range_pct": sideways_decision.traded_value_range_pct,
                    "sideways_avg_abs_return_pct": sideways_decision.avg_abs_return_pct,
                    "sideways_min_scale_in_price": sideways_decision.min_scale_in_price,
                    "no_trade_relaxed": relaxed_signal,
                    "trade_logic_update_trace": trade_logic_update_trace,
                    **rule_variant,
                },
            )
        if relaxed_signal and decision.sizing.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT":
            decision = self._trade_decision_service.evaluate(
                self._build_decision_request(snapshot.trade_price, relax_fee_edge=True),
            )
            variant_payload = self._run_demo_rule_variant_shadow(decision=decision, current_price=snapshot.trade_price)
            available_cash = self._demo_cash_balance if self._trading_mode == "demo" else portfolio.cash_balance
            decision = self._apply_variant_and_gate_entry(
                decision=decision,
                variant_payload=variant_payload,
                current_price=snapshot.trade_price,
                position_exists=position is not None,
                available_cash=available_cash,
            )
            box_range_opportunity = self._box_range_buy_opportunity(
                market_state=decision.regime.market_state,
                box_range_low=decision.regime.box_range_low,
                box_range_high=decision.regime.box_range_high,
                current_price=snapshot.trade_price,
                position_exists=position is not None,
            )
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
                **market_state_extra,
                **rule_variant,
            },
        )
        scale_in_limit = self._scale_in_limit_decision(position=position, decision=decision, current_price=snapshot.trade_price)
        if not scale_in_limit["allowed"]:
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason=str(scale_in_limit["reason_code"]),
                extra={
                    "entry_type": "scale_in",
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "previous_entry_signal_level": self._previous_entry_signal_level(position),
                    "previous_entry_signal_score": self._last_entry_signal_score,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "scale_in_count": self._scale_in_count,
                    "scale_in_max_entries": self._config.scale_in_max_entries,
                    "market_state": decision.regime.market_state,
                    "market_state_label": decision.regime.market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    **market_state_extra,
                    "no_trade_relaxed": relaxed_signal,
                    "trade_logic_update_trace": trade_logic_update_trace,
                    **rule_variant,
                },
            )
        decision = scale_in_limit["decision"]
        scale_in_cap_applied = bool(scale_in_limit.get("cap_applied"))
        scale_in_original_buy_amount = scale_in_limit.get("original_buy_amount")
        if self._scale_in_signal_not_stronger(position=position, decision=decision):
            rule_variant = self._variant_extra(variant_payload)
            self._consecutive_entry_blocks += 1
            return self._record_cycle(
                status="blocked",
                reason="SCALE_IN_SIGNAL_NOT_STRONGER",
                extra={
                    "entry_type": "scale_in",
                    "signal_level": decision.signal.level,
                    "signal_score": decision.signal.score,
                    "signal_blocked": decision.signal.blocked,
                    "signal_reason_codes": decision.signal.reason_codes,
                    "previous_entry_signal_level": self._previous_entry_signal_level(position),
                    "previous_entry_signal_score": self._last_entry_signal_score,
                    "sizing_allowed": decision.sizing.allowed,
                    "sizing_blocked_reason": decision.sizing.blocked_reason,
                    "buy_amount": 0.0,
                    "market_state": decision.regime.market_state,
                    "market_state_label": decision.regime.market_state_label,
                    "box_range_low": decision.regime.box_range_low,
                    "box_range_high": decision.regime.box_range_high,
                    **market_state_extra,
                    "no_trade_relaxed": relaxed_signal,
                    "trade_logic_update_trace": trade_logic_update_trace,
                    **rule_variant,
                },
            )
        if self._trading_mode == "demo" and decision.sizing.allowed and decision.sizing.buy_amount > 0 and not self._can_afford_demo_buy(decision.sizing.buy_amount):
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
                **market_state_extra,
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
            self._last_trade_filled_at = self._clock()   # 24시간 무거래 추적용
            self._consecutive_entry_blocks = 0
            self._last_entry_signal_level = decision.signal.level
            self._last_entry_signal_score = decision.signal.score
            if entry_type == "scale_in":
                self._scale_in_count += 1
            else:
                self._scale_in_count = 0

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
                **market_state_extra,
                "no_trade_relaxed": relaxed_signal,
                "log_backed_bull_weak_recovery": log_backed_recovery,
                "trade_logic_update_trace": trade_logic_update_trace,
                **self._box_range_extra(box_range_opportunity),
                "post_fill_position_opened": post_fill_result.position is not None,
                "scale_in_count": self._scale_in_count,
                "scale_in_cap_applied": scale_in_cap_applied,
                "scale_in_original_buy_amount": scale_in_original_buy_amount,
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
        trend = self._classify_current_market_state(current_price)
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
            recent_loss_streak=(
                0
                if self._execution_ledger is None
                else self._execution_ledger.recent_loss_streak()
            ),
            relax_fee_edge=relax_fee_edge,
            external_context_weight=self._external_context_weight(external_context),
            observed_market_state=trend.market_state,
            observed_market_state_label=trend.market_state_label,
            observed_box_range_low=trend.box_range_low,
            observed_box_range_high=trend.box_range_high,
        )

    def _daily_loss_guard_decision(self) -> dict[str, object]:
        max_daily_loss = max(float(self._config.max_daily_loss), 0.0)
        if max_daily_loss <= 0 or self._execution_ledger is None:
            return {"allowed": True}
        trading_date = self._clock().date()
        realized_pnl = self._execution_ledger.realized_pnl_for_date(trading_date)
        if realized_pnl > -max_daily_loss:
            return {
                "allowed": True,
                "daily_realized_pnl": realized_pnl,
                "daily_loss_limit": max_daily_loss,
                "trading_date": trading_date.isoformat(),
            }
        return {
            "allowed": False,
            "daily_realized_pnl": realized_pnl,
            "daily_loss_limit": max_daily_loss,
            "trading_date": trading_date.isoformat(),
        }

    def _classify_current_market_state(
        self,
        current_price: float,
        *,
        reference_change_pct: float | None = None,
    ):
        reference = self._last_ticker_reference_change_pct if reference_change_pct is None else reference_change_pct
        return self._trend_classifier.classify(
            current_price=current_price,
            history=self._market_price_store.list_history(self._market),
            learning_events=self._learning_service.recent_events(limit=200),
            reference_change_pct=reference,
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
        payload = self._demo_rule_variant_shadow_tester.evaluate(
            decision=decision,
            current_price=current_price,
            portfolio=self._portfolio_state(),
        )
        self._notify_rule_variant_change_if_needed(payload)
        self._record_variant_diagnostic_events(payload)
        return payload

    def _record_variant_diagnostic_events(self, payload: dict[str, object] | None) -> None:
        """Fallback Leader 선발·시장 전환 등 진단에 유용한 섀도 평가 이벤트를 기록한다."""
        if payload is None:
            return
        selection_type = payload.get("selection_type")
        results = payload.get("results", [])

        # ── 1) fallback_leader_selected: 임시 리더 선발 시 기록 ──────────────────
        if selection_type == "fallback_leader" and payload.get("is_fallback_leader"):
            self._learning_service.record(
                LearningEvent(
                    event_name="fallback_leader_selected",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "leader_key": payload.get("leader_key"),
                        "leader_label": payload.get("leader_label"),
                        "leader_reason": payload.get("leader_reason"),
                        "market_state": payload.get("market_state"),
                        "market_state_label": payload.get("market_state_label"),
                        # 전체 룰 현황 스냅샷 (왜 이 룰이 선발됐는지 맥락)
                        "all_variants_summary": [
                            {
                                "key": r.get("variant_key"),
                                "label": r.get("variant_label"),
                                "profit_rate": r.get("profit_rate"),
                                "stop_loss_rate": r.get("stop_loss_rate"),
                                "stop_loss_count": r.get("stop_loss_count"),
                                "trade_count": r.get("trade_count"),
                                "profit_factor": r.get("profit_factor"),
                                "promotion_eligible": r.get("promotion_eligible"),
                                "max_drawdown_pct": r.get("max_drawdown_pct"),
                            }
                            for r in results
                        ],
                    },
                )
            )

        # ── 2) variant_portfolio_snapshot: 매 평가마다 전 룰 포트폴리오 요약 기록 ──
        # 너무 잦은 기록을 막기 위해 약 5분(100틱)에 1회만 기록
        tick = getattr(self, "_variant_snapshot_tick_counter", 0) + 1
        self._variant_snapshot_tick_counter = tick
        if tick % 100 == 1:
            self._learning_service.record(
                LearningEvent(
                    event_name="variant_portfolio_snapshot",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "leader_key": payload.get("leader_key"),
                        "is_fallback_leader": payload.get("is_fallback_leader", False),
                        "selection_type": selection_type,
                        "bear_to_bull_score": payload.get("bear_to_bull_score"),
                        "bull_to_bear_score": payload.get("bull_to_bear_score"),
                        "bear_to_bull_confirmed": payload.get("bear_to_bull_confirmed"),
                        "bull_to_bear_confirmed": payload.get("bull_to_bear_confirmed"),
                        "variants": [
                            {
                                "key": r.get("variant_key"),
                                "profit_rate": r.get("profit_rate"),
                                "realized_pnl": r.get("realized_pnl"),
                                "trade_count": r.get("trade_count"),
                                "stop_loss_count": r.get("stop_loss_count"),
                                "profit_factor": r.get("profit_factor"),
                                "promotion_eligible": r.get("promotion_eligible"),
                            }
                            for r in results
                        ],
                    },
                )
            )

        # ── 3) market_transition_detected: 시장 전환 감지 시 기록 ──────────────────
        b2b_confirmed = payload.get("bear_to_bull_confirmed", False)
        bu2be_confirmed = payload.get("bull_to_bear_confirmed", False)
        prev_b2b = getattr(self, "_last_bear_to_bull_confirmed", False)
        prev_bu2be = getattr(self, "_last_bull_to_bear_confirmed", False)

        if b2b_confirmed and not prev_b2b:
            # bear→bull 전환 새로 감지
            self._learning_service.record(
                LearningEvent(
                    event_name="market_transition_detected",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "transition": "bear_to_bull",
                        "bear_to_bull_score": payload.get("bear_to_bull_score"),
                        "bull_to_bear_score": payload.get("bull_to_bear_score"),
                        "market_state": payload.get("market_state"),
                        "dynamic_box_low": payload.get("dynamic_box_low"),
                        "dynamic_box_high": payload.get("dynamic_box_high"),
                        "leader_key": payload.get("leader_key"),
                    },
                )
            )
        elif bu2be_confirmed and not prev_bu2be:
            # bull→bear 전환 새로 감지
            self._learning_service.record(
                LearningEvent(
                    event_name="market_transition_detected",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "transition": "bull_to_bear",
                        "bear_to_bull_score": payload.get("bear_to_bull_score"),
                        "bull_to_bear_score": payload.get("bull_to_bear_score"),
                        "market_state": payload.get("market_state"),
                        "dynamic_box_low": payload.get("dynamic_box_low"),
                        "dynamic_box_high": payload.get("dynamic_box_high"),
                        "leader_key": payload.get("leader_key"),
                    },
                )
            )
        self._last_bear_to_bull_confirmed = b2b_confirmed
        self._last_bull_to_bear_confirmed = bu2be_confirmed


    def _notify_rule_variant_change_if_needed(
        self,
        variant_payload: dict[str, object],
    ) -> None:
        if not variant_payload.get("selection_changed") or self._telegram_notifier is None:
            return
        notify_rule_changed = getattr(
            self._telegram_notifier,
            "notify_rule_variant_changed",
            None,
        )
        if notify_rule_changed is None:
            return
        applied_label = variant_payload.get("applied_variant_label")
        applied_profit_rate = variant_payload.get("applied_variant_profit_rate")
        if not applied_label or applied_profit_rate is None:
            return
        notify_rule_changed(
            market=self._market,
            mode=self._trading_mode,
            previous_variant_label=variant_payload.get("previous_variant_label"),
            previous_profit_rate=variant_payload.get("previous_variant_profit_rate"),
            applied_variant_label=str(applied_label),
            applied_profit_rate=float(applied_profit_rate),
            selection_type=variant_payload.get("selection_type"),
            reason=str(variant_payload.get("leader_reason") or "성과 비교 결과"),
        )

    def _apply_variant_and_gate_entry(
        self,
        *,
        decision: TradeDecisionResult,
        variant_payload: dict[str, object] | None,
        current_price: float,
        position_exists: bool,
        available_cash: float,
    ) -> TradeDecisionResult:
        has_applied_rule = False
        is_fallback_leader = False
        if variant_payload is not None:
            applied_key = variant_payload.get("leader_key")
            if applied_key:
                has_applied_rule = True
                is_fallback_leader = bool(variant_payload.get("is_fallback_leader", False))
                decision = self._demo_rule_variant_shadow_tester.apply_selected_variant(
                    decision=decision,
                    current_price=current_price,
                    available_cash=available_cash,
                )
                # ── Fallback Leader 모드: 매수 크기 50% 축소 ────────────────────────
                # 정상 승격 룰이 없어 임시 리더를 사용 중. 손실 위험을 줄이기 위해
                # 매수 금액을 절반으로 축소하여 보수적으로 운용한다.
                if is_fallback_leader and not position_exists:
                    from app.services.trading.variants import DemoRuleVariantShadowTester
                    scale = DemoRuleVariantShadowTester.FALLBACK_LEADER_BUY_SCALE
                    new_buy_amount = decision.sizing.buy_amount * scale
                    new_buy_quantity = decision.sizing.buy_quantity * scale
                    new_buy_ratio = decision.sizing.buy_ratio * scale
                    decision = replace(
                        decision,
                        sizing=replace(
                            decision.sizing,
                            buy_amount=new_buy_amount,
                            buy_quantity=new_buy_quantity,
                            buy_ratio=new_buy_ratio,
                            blocked_reason=None,  # 차단 해제
                        ),
                    )

        # 플러스 검증된 대표 룰이 적용되지 않은 상태에서 신규 매수 진입 시도인 경우 대기 및 차단
        if not has_applied_rule and not position_exists:
            decision = replace(
                decision,
                sizing=replace(
                    decision.sizing,
                    allowed=False,
                    buy_ratio=0.0,
                    buy_amount=0.0,
                    buy_quantity=0.0,
                    blocked_reason="NO_POSITIVE_RULE_LEADER_YET",
                )
            )
        return decision

    @staticmethod
    def _variant_extra(variant_payload: dict[str, object] | None) -> dict[str, object]:
        if variant_payload is None:
            return {}
        return {
            "rule_variant_shadow": variant_payload,
            "rule_variant_leader_key": variant_payload.get("leader_key"),
            "rule_variant_leader_label": variant_payload.get("leader_label"),
            "rule_variant_leader_reason": variant_payload.get("leader_reason"),
            "rule_variant_selection_changed": variant_payload.get("selection_changed", False),
            "rule_variant_candidate_key": variant_payload.get("candidate_leader_key"),
        }

    @staticmethod
    def _market_state_extra(decision) -> dict[str, object]:
        return {
            "market_state_entry_allowed": decision.allowed,
            "market_state_entry_reason": decision.reason_code,
            "market_state_transition_boost": decision.transition_boost,
            "previous_market_state": decision.previous_market_state,
            "market_state_transition": decision.transition,
            "market_state_confirmation_count": decision.current_state_count,
        }


    def _trade_logic_update_trace(
        self,
        *,
        decision,
        variant_payload: dict[str, object] | None,
        entry_type: str,
        market_state: str,
        historical_loss_guard: dict[str, object],
        log_backed_recovery: bool,
    ) -> dict[str, object]:
        leader_key = variant_payload.get("leader_key") if isinstance(variant_payload, dict) else None
        baseline_block_reason = None if historical_loss_guard.get("allowed") else historical_loss_guard.get("reason_code")
        return {
            "version": "2026-06-07-loss-aware-weak-recovery-guard",
            "purpose": "track_optimization_effect_for_future_rule_reviews",
            "applied": bool(log_backed_recovery),
            "candidate": bool(
                entry_type == "initial"
                and market_state == "bull"
                and decision.signal.level == "weak"
                and decision.signal.score >= 0.24
            ),
            "baseline_block_reason": baseline_block_reason,
            "entry_type": entry_type,
            "market_state": market_state,
            "signal_level": decision.signal.level,
            "signal_score": decision.signal.score,
            "sizing_allowed_before_relax": decision.sizing.allowed,
            "sizing_blocked_reason_before_relax": decision.sizing.blocked_reason,
            "rule_variant_leader_key": leader_key,
            "consecutive_entry_blocks": self._consecutive_entry_blocks,
            "optimization_metric_keys": [
                "filled_after_recovery",
                "blocked_after_recovery",
                "post_fill_position_opened",
                "replay_final_profit_rate",
                "demo_realized_pnl",
                "rule_variant_stop_loss_count",
                "rule_variant_max_drawdown_pct",
                "weak_recovery_risk_blocked",
            ],
        }

    def _post_sell_reentry_confirmation(
        self,
        *,
        reentry_decision,
        decision,
        market_state_entry,
        current_price: float,
        entry_type: str,
    ) -> dict[str, object]:
        stop_loss_confirmation = self._post_stop_loss_reentry_confirmation(
            reentry_decision=reentry_decision,
            decision=decision,
            market_state_entry=market_state_entry,
            current_price=current_price,
            entry_type=entry_type,
        )
        # ── 5) reentry_block_released: 손절 후 차단 해제 시 진단 이벤트 기록 ─────
        if stop_loss_confirmation.get("post_stop_loss_reentry_confirmed"):
            self._learning_service.record(
                LearningEvent(
                    event_name="reentry_block_released",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "reentry_mode": stop_loss_confirmation.get("post_stop_loss_reentry_mode"),
                        "last_exit_reason_code": stop_loss_confirmation.get("post_stop_loss_last_exit_reason_code"),
                        "last_exit_price": stop_loss_confirmation.get("post_stop_loss_last_exit_price"),
                        "current_price": current_price,
                        "required_recovery_price": stop_loss_confirmation.get("post_stop_loss_required_recovery_price"),
                        "market_state": market_state_entry.current_market_state,
                        "market_state_count": market_state_entry.current_state_count,
                        "signal_level": decision.signal.level,
                        "signal_score": decision.signal.score,
                        "entry_type": entry_type,
                        "elapsed_hours": stop_loss_confirmation.get("post_stop_loss_elapsed_hours"),
                    },
                )
            )
        if not stop_loss_confirmation.get("allowed", True) or stop_loss_confirmation.get("post_stop_loss_reentry_confirmed"):
            return stop_loss_confirmation
        if entry_type != "initial" or reentry_decision.last_exit_price is None:
            return {"allowed": True}
        last_exit_price = float(reentry_decision.last_exit_price)
        if last_exit_price <= 0 or current_price <= 0:
            return {"allowed": True}
        min_reentry_edge_pct = max((self._config.trading_fee_rate * 2) + 0.001, 0.0015)
        required_pullback_price = round(last_exit_price * (1 - min_reentry_edge_pct), 4)
        required_breakout_price = round(last_exit_price * (1 + self._config.market_recovery_change_pct), 4)
        # Legacy: requires at least market_recovery_confirmation_ticks of confirmed bull.
        required_confirmation_count = max(
            self._config.market_recovery_confirmation_ticks,
            self._config.market_state_transition_confirmation_ticks,
            1,
        )
        strong_signal = decision.signal.level in {"strong", "very_strong"} and decision.signal.score >= 0.65
        medium_signal = decision.signal.level == "medium" and decision.signal.score >= 0.4
        confirmed_bull_strict = (
            market_state_entry.current_market_state == "bull"
            and market_state_entry.current_state_count >= required_confirmation_count
        )
        confirmed_bull_relaxed = (
            market_state_entry.current_market_state == "bull"
            and market_state_entry.current_state_count >= 1
        )
        cheaper_reentry = current_price <= required_pullback_price
        confirmed_breakout = confirmed_bull_strict and strong_signal and current_price >= required_breakout_price
        uptrend_continuation = (
            (strong_signal or medium_signal)
            and confirmed_bull_strict
            and current_price >= last_exit_price
        )
        if cheaper_reentry or confirmed_breakout or uptrend_continuation:
            if cheaper_reentry:
                mode = "pullback"
            elif uptrend_continuation and not confirmed_breakout:
                mode = "uptrend_continuation"
            else:
                mode = "confirmed_bull_breakout"
            return {
                "allowed": True,
                "post_sell_reentry_edge_confirmed": True,
                "post_sell_reentry_mode": mode,
                "post_sell_last_exit_reason_code": reentry_decision.last_exit_reason_code,
                "post_sell_last_exit_price": last_exit_price,
                "post_sell_required_pullback_price": required_pullback_price,
                "post_sell_required_breakout_price": required_breakout_price,
            }
        return {
            "allowed": False,
            "reason_code": "POST_SELL_REENTRY_EDGE_REQUIRED",
            "post_sell_reentry_edge_confirmed": False,
            "post_sell_last_exit_reason_code": reentry_decision.last_exit_reason_code,
            "post_sell_last_exit_price": last_exit_price,
            "post_sell_required_pullback_price": required_pullback_price,
            "post_sell_required_breakout_price": required_breakout_price,
            "post_sell_min_reentry_edge_pct": round(min_reentry_edge_pct, 6),
            "post_sell_confirmed_bull": confirmed_bull_strict,
            "post_sell_confirmed_bull_relaxed": confirmed_bull_relaxed,
            "post_sell_strong_signal": strong_signal,
            "post_sell_medium_signal": medium_signal,
        }

    def _post_stop_loss_reentry_confirmation(
        self,
        *,
        reentry_decision,
        decision,
        market_state_entry,
        current_price: float,
        entry_type: str,
    ) -> dict[str, object]:
        reason_code = reentry_decision.last_exit_reason_code
        if reason_code is None or not str(reason_code).startswith("STOP_LOSS"):
            return {"allowed": True}

        # ── 손절 이후 최대 차단 시간 초과 시 자동 해제 ───────────────────────────────────
        last_exit_time = reentry_decision.last_exit_time
        if last_exit_time is not None and self._config.post_stop_loss_max_block_hours > 0:
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            try:
                if isinstance(last_exit_time, str):
                    last_exit_time = datetime.datetime.fromisoformat(last_exit_time)
                elapsed_hours = (now - last_exit_time).total_seconds() / 3600
                if elapsed_hours >= self._config.post_stop_loss_max_block_hours:
                    return {
                        "allowed": True,
                        "post_stop_loss_reentry_confirmed": True,
                        "post_stop_loss_reentry_mode": "max_block_hours_expired",
                        "post_stop_loss_elapsed_hours": round(elapsed_hours, 2),
                        "post_stop_loss_last_exit_reason_code": reason_code,
                    }
            except Exception:
                pass  # 시간 파싱 실패 시 타 조건으로 판단
        # ───────────────────────────────────────────────────────────────────────────
        required_confirmation_count = max(
            self._config.market_recovery_confirmation_ticks,
            self._config.market_state_transition_confirmation_ticks,
            1,
        )
        last_exit_price = reentry_decision.last_exit_price

        # ── 가격 회복 기준 개선 ──────────────────────────────────────────────────
        # 현재가감 손절가보다 낙은 경우, 손절가 기준으로 회복함을 요구하면
        # 영구 차단되므로 현재가 기준으로 계산
        if last_exit_price is not None and last_exit_price > 0:
            if current_price < last_exit_price:
                # 손절가보다 난 아래에 있음: 현재가에서 조세한 상승만 확인
                base_price = current_price
            else:
                # 손절가 이상: 손절가에서 조세한 상승 확인
                base_price = last_exit_price
        else:
            base_price = None

        required_recovery_price = (
            None
            if base_price is None
            else round(base_price * (1 + self._config.market_recovery_change_pct), 4)
        )
        strong_signal = decision.signal.level in {"strong", "very_strong"} and decision.signal.score >= 0.65
        sizing = getattr(decision, "sizing", None)
        sizing_allowed = True if sizing is None else bool(getattr(sizing, "allowed", False))
        strong_recovery_price = (
            None
            if base_price is None
            else round(base_price * (1 + max(self._config.market_recovery_change_pct, 0.003)), 4)
        )
        confirmed_bull_strict = (
            entry_type == "initial"
            and market_state_entry.current_market_state == "bull"
            and market_state_entry.current_state_count >= required_confirmation_count
        )
        confirmed_bear_to_bull_reversal = (
            entry_type == "initial"
            and getattr(market_state_entry, "transition", None) == "bear->bull"
            and market_state_entry.current_market_state == "bull"
            and market_state_entry.current_state_count >= required_confirmation_count
        )
        medium_reversal_signal = (
            decision.signal.level == "medium"
            and decision.signal.score >= 0.4
            and sizing_allowed
        )
        recovered_price = required_recovery_price is None or current_price >= required_recovery_price
        
        # 상승장(bull)이면서 손절가 위로 가격이 완전히 회복되었다면, 
        # 무리하게 강한 신호(strong_signal)를 요구하지 않고 
        # 룰이 허용한 일반 진입 신호(sizing_allowed)만으로도 재진입을 허용합니다.
        if confirmed_bull_strict and recovered_price and sizing_allowed:
            return {
                "allowed": True,
                "post_stop_loss_reentry_confirmed": True,
                "post_stop_loss_reentry_mode": "recovered_bull",
                "post_stop_loss_required_confirmation_count": required_confirmation_count,
                "post_stop_loss_required_recovery_price": required_recovery_price,
                "post_stop_loss_strong_recovery_price": strong_recovery_price,
                "post_stop_loss_last_exit_reason_code": reason_code,
                "post_stop_loss_last_exit_price": last_exit_price,
            }
        if confirmed_bear_to_bull_reversal and recovered_price and medium_reversal_signal:
            return {
                "allowed": True,
                "post_stop_loss_reentry_confirmed": True,
                "post_stop_loss_reentry_mode": "confirmed_bear_to_bull_reversal",
                "post_stop_loss_required_confirmation_count": required_confirmation_count,
                "post_stop_loss_required_recovery_price": required_recovery_price,
                "post_stop_loss_strong_recovery_price": strong_recovery_price,
                "post_stop_loss_last_exit_reason_code": reason_code,
                "post_stop_loss_last_exit_price": last_exit_price,
                "post_stop_loss_confirmed_bear_to_bull_reversal": True,
            }
        return {
            "allowed": False,
            "reason_code": "POST_STOP_LOSS_REENTRY_CONFIRMATION_REQUIRED",
            "post_stop_loss_reentry_confirmed": False,
            "post_stop_loss_required_confirmation_count": required_confirmation_count,
            "post_stop_loss_required_recovery_price": required_recovery_price,
            "post_stop_loss_strong_recovery_price": strong_recovery_price,
            "post_stop_loss_last_exit_reason_code": reason_code,
            "post_stop_loss_last_exit_price": last_exit_price,
            "post_stop_loss_confirmed_bull": confirmed_bull_strict,
            "post_stop_loss_confirmed_bear_to_bull_reversal": confirmed_bear_to_bull_reversal,
            "post_stop_loss_strong_signal": strong_signal,
            "post_stop_loss_medium_reversal_signal": medium_reversal_signal,
            "post_stop_loss_recovered_price": recovered_price,
            "post_stop_loss_sizing_allowed": sizing_allowed,
        }

    def _log_backed_bull_weak_recovery(
        self,
        *,
        decision,
        variant_payload: dict[str, object] | None,
        entry_type: str,
        market_state: str,
    ) -> bool:
        if entry_type != "initial" or market_state != "bull":
            return False
        if decision.signal.blocked:
            return False
        if decision.signal.level == "medium" and "BULL_MARKET_PARTICIPATION_BOOST" in decision.signal.reason_codes:
            return decision.sizing.allowed or decision.sizing.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT"
        if decision.signal.level != "weak" or decision.signal.score < 0.24:
            return False
        if self._active_historical_loss_profile() is not None:
            return False
        if not isinstance(variant_payload, dict) or variant_payload.get("leader_key") != "B":
            return False
        if self._consecutive_entry_blocks < max(self._config.no_trade_relax_after_cycles, 1):
            return False
        return decision.sizing.allowed or decision.sizing.blocked_reason == "FEE_ADJUSTED_EDGE_LIMIT"

    def _historical_loss_guard_decision(
        self,
        *,
        entry_type: str,
        signal_level: str,
        signal_score: float,
        box_range_opportunity: dict[str, object],
    ) -> dict[str, object]:
        profile = self._active_historical_loss_profile()
        if profile is None or signal_level != "weak":
            return {"allowed": True}

        box_entry_allowed = bool(box_range_opportunity.get("allowed"))
        if entry_type == "scale_in":
            return {
                "allowed": False,
                "reason_code": "WEAK_SCALE_IN_HISTORICAL_LOSS_BLOCK",
                "profile": profile,
                "box_entry_allowed": box_entry_allowed,
            }
        if (not box_entry_allowed) or signal_score < self._config.historical_loss_guard_box_entry_min_score:
            return {
                "allowed": False,
                "reason_code": "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK",
                "profile": profile,
                "box_entry_allowed": box_entry_allowed,
            }
        return {"allowed": True}

    def _active_historical_loss_profile(self) -> ExecutionPerformanceProfile | None:
        if not self._config.historical_loss_guard_enabled:
            return None
        profile = self._execution_ledger.performance_profile() if self._execution_ledger is not None else None
        learning_profile = self._learning_stop_loss_profile()
        if profile is None and learning_profile is None:
            return None
        if profile is None:
            return learning_profile
        if learning_profile is None:
            return self._active_ledger_loss_profile(profile)
        ledger_profile = self._active_ledger_loss_profile(profile)
        if ledger_profile is None:
            return learning_profile
        if learning_profile.stop_loss_count > ledger_profile.stop_loss_count:
            return learning_profile
        return ledger_profile

    def _active_ledger_loss_profile(self, profile: ExecutionPerformanceProfile) -> ExecutionPerformanceProfile | None:
        fill_count = profile.buy_count + profile.sell_count
        if fill_count < self._config.historical_loss_guard_min_fills:
            return None
        if profile.stop_loss_count <= 0 or profile.stop_loss_pnl >= 0:
            return None
        if profile.weak_buy_ratio < self._config.historical_loss_guard_weak_buy_ratio:
            return None
        if profile.stop_loss_to_profit_ratio < self._config.historical_loss_guard_stop_loss_to_profit_ratio:
            return None
        return profile

    def _learning_stop_loss_profile(self) -> ExecutionPerformanceProfile | None:
        buy_count = 0
        weak_buy_count = 0
        stop_loss_count = 0
        weak_stop_loss_count = 0
        recent_stop_loss_reason = None
        for event in self._learning_service.recent_events(limit=500):
            payload = event.payload if isinstance(event.payload, dict) else {}
            if event.event_name == "position_opened":
                buy_count += 1
                if payload.get("signal_level") == "weak":
                    weak_buy_count += 1
                continue
            if event.event_name != "position_lifecycle_updated" or payload.get("event_type") != "closed":
                continue
            reason_code = str(payload.get("reason_code") or "")
            signal_level = str(payload.get("signal_level") or "")
            if not reason_code.startswith("STOP_LOSS"):
                continue
            stop_loss_count += 1
            recent_stop_loss_reason = reason_code
            if signal_level == "weak":
                weak_stop_loss_count += 1

        if stop_loss_count < self._config.historical_loss_guard_min_learning_stop_losses:
            return None
        if weak_stop_loss_count <= 0:
            return None
        weak_buy_ratio = 0.0 if buy_count <= 0 else weak_buy_count / buy_count
        if weak_buy_ratio < self._config.historical_loss_guard_weak_buy_ratio:
            return None
        return ExecutionPerformanceProfile(
            realized_pnl=0.0,
            regular_sell_pnl=0.0,
            stop_loss_pnl=-float(stop_loss_count),
            buy_count=buy_count,
            weak_buy_count=weak_buy_count,
            sell_count=stop_loss_count,
            stop_loss_count=stop_loss_count,
            weak_buy_ratio=round(weak_buy_ratio, 4),
            stop_loss_to_profit_ratio=float("inf"),
            recent_stop_loss_reason=recent_stop_loss_reason,
        )

    @staticmethod
    def _historical_loss_guard_extra(decision: dict[str, object]) -> dict[str, object]:
        profile = decision.get("profile")
        if not isinstance(profile, ExecutionPerformanceProfile):
            return {}
        return {
            "historical_loss_guard_active": True,
            "historical_loss_guard_regular_sell_pnl": profile.regular_sell_pnl,
            "historical_loss_guard_stop_loss_pnl": profile.stop_loss_pnl,
            "historical_loss_guard_realized_pnl": profile.realized_pnl,
            "historical_loss_guard_weak_buy_ratio": profile.weak_buy_ratio,
            "historical_loss_guard_stop_loss_to_profit_ratio": profile.stop_loss_to_profit_ratio,
            "historical_loss_guard_recent_stop_loss_reason": profile.recent_stop_loss_reason,
            "historical_loss_guard_box_entry_allowed": bool(decision.get("box_entry_allowed")),
        }

    def _recent_price_market_state(self) -> str | None:
        history = self._market_price_store.list_history(self._market)
        prices = [item.price for item in history if item.price > 0]
        if len(prices) < 2:
            return None
        try:
            return self._classify_current_market_state(prices[-1]).market_state
        except Exception:
            return None

    def _box_range_buy_opportunity(
        self,
        *,
        market_state: str,
        box_range_low: float | None,
        box_range_high: float | None,
        current_price: float,
        position_exists: bool,
    ) -> dict[str, object]:
        if position_exists or market_state != "box" or box_range_low is None or box_range_high is None:
            return {"allowed": False}
        if current_price <= 0 or box_range_low <= 0 or box_range_high <= box_range_low:
            return {"allowed": False}
        box_width = box_range_high - box_range_low
        box_width_pct = box_width / box_range_low
        # Minimum required width: round-trip fee + minimum net profit edge.
        # Raised from 0.3% to 0.5% to filter out narrow ranges (e.g. < 10 KRW)
        # that cannot yield a meaningful profit after fees.
        min_required_pct = (self._config.trading_fee_rate * 2) + 0.005
        if box_width_pct < min_required_pct:
            return {
                "allowed": False,
                "box_range_width_pct": round(box_width_pct, 6),
                "box_range_required_pct": round(min_required_pct, 6),
                "box_range_too_narrow": True,
            }
        # Also enforce an absolute minimum width in KRW terms: the range must
        # be at least 0.5% of the current price to be actionable.
        min_absolute_width = current_price * 0.005
        if box_width < min_absolute_width:
            return {
                "allowed": False,
                "box_range_width_pct": round(box_width_pct, 6),
                "box_range_required_pct": round(min_required_pct, 6),
                "box_range_absolute_too_narrow": True,
            }
        buy_zone_high = box_range_low + (box_width * 0.25)
        return {
            "allowed": current_price <= buy_zone_high,
            "box_range_width_pct": round(box_width_pct, 6),
            "box_range_required_pct": round(min_required_pct, 6),
            "box_range_buy_zone_high": round(buy_zone_high, 4),
        }

    @staticmethod
    def _box_range_extra(opportunity: dict[str, object]) -> dict[str, object]:
        return {
            "box_range_buy_opportunity": bool(opportunity.get("allowed")),
            "box_range_width_pct": opportunity.get("box_range_width_pct"),
            "box_range_required_pct": opportunity.get("box_range_required_pct"),
            "box_range_buy_zone_high": opportunity.get("box_range_buy_zone_high"),
        }


    def _scale_in_limit_decision(self, *, position, decision, current_price: float) -> dict[str, object]:
        if position is None:
            return {"allowed": True, "decision": decision, "cap_applied": False, "original_buy_amount": None}
        max_entries = max(int(self._config.scale_in_max_entries), 0)
        if self._scale_in_count >= max_entries:
            return {"allowed": False, "reason_code": "SCALE_IN_MAX_ENTRIES", "decision": decision}
        if not decision.sizing.allowed or decision.sizing.buy_amount <= 0 or current_price <= 0:
            return {"allowed": True, "decision": decision, "cap_applied": False, "original_buy_amount": None}
        current_notional = max(position.entry_price * position.quantity, 0.0)
        max_scale_in_amount = current_notional * max(float(self._config.scale_in_max_position_multiplier), 0.0)
        if max_scale_in_amount <= 0 or decision.sizing.buy_amount <= max_scale_in_amount:
            return {"allowed": True, "decision": decision, "cap_applied": False, "original_buy_amount": None}
        adjusted_amount = round(max_scale_in_amount, 1)
        adjusted_sizing = replace(
            decision.sizing,
            buy_amount=adjusted_amount,
            buy_quantity=round(adjusted_amount / current_price, 4),
        )
        return {
            "allowed": True,
            "decision": replace(decision, sizing=adjusted_sizing),
            "cap_applied": True,
            "original_buy_amount": decision.sizing.buy_amount,
        }

    def _scale_in_allowed(self, *, position, current_price: float) -> bool:
        if not self._config.scale_in_enabled:
            return False
        if current_price <= 0 or position.entry_price <= 0:
            return False
        # 기본은 평균 단가 이하의 pullback 분할매수다. 상승장에서는 가격·거래대금이
        # 함께 늘고 단기 고점 갱신이 확인된 경우에만 작은 premium 추가매수를 허용한다.
        pullback_limit = position.entry_price * (1 + self._config.scale_in_max_price_premium_pct)
        if current_price <= pullback_limit:
            return True
        if not self._config.bull_scale_in_enabled:
            return False
        premium_limit = position.entry_price * (1 + self._config.bull_scale_in_max_price_premium_pct)
        if current_price > premium_limit or len(self._prices) < 3 or len(self._traded_values) < 3:
            return False
        market_state = self._classify_current_market_state(current_price).market_state
        previous_value_avg = sum(list(self._traded_values)[:-1]) / max(len(self._traded_values) - 1, 1)
        traded_value_multiple = (
            self._traded_values[-1] / previous_value_avg if previous_value_avg > 0 else 1.0
        )
        price_breakout_confirmed = current_price > self._prices[-2] and current_price > self._prices[-3]
        return (
            market_state == "bull"
            and price_breakout_confirmed
            and traded_value_multiple >= self._config.bull_scale_in_min_traded_value_multiple
        )

    def _scale_in_signal_not_stronger(self, *, position, decision) -> bool:
        if position is None:
            return False
        if self._last_entry_signal_score is not None:
            return decision.signal.score <= self._last_entry_signal_score + 1e-9
        previous_level = self._previous_entry_signal_level(position)
        return self._signal_level_rank(decision.signal.level) <= self._signal_level_rank(previous_level)

    def _previous_entry_signal_level(self, position) -> str | None:
        return self._last_entry_signal_level or getattr(position, "signal_level", None)

    @staticmethod
    def _signal_level_rank(level: str | None) -> int:
        return {
            "weak": 1,
            "medium": 2,
            "strong": 3,
            "very_strong": 4,
        }.get(str(level or ""), 0)

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
            "market_window": self._market_window_summary(),
        }
        external_context = self._external_context()
        if external_context is not None:
            payload["external_context"] = external_context
        if extra is not None:
            payload.update(extra)
        for key, value in self._market_regime_payload().items():
            payload.setdefault(key, value)
        self._last_cycle = dict(payload)
        self._learning_service.record(
            LearningEvent(
                event_name="auto_trade_cycle",
                market=self._market,
                mode=self._trading_mode,
                payload=payload,
            ),
        )
        if self._auto_rule_update_service is not None and self._should_check_auto_rule_update():
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
        self._maybe_record_daily_rule_summary()
        return payload

    def _maybe_record_daily_rule_summary(self) -> None:
        """하루 1회 룰별 섀도 포트폴리오 성과 요약을 기록한다.

        rule_performance_daily_summary 이벤트를 사용해 날별 성과 추이를 분석하고
        어떤 룰이 어느 시점에 성과가 좋았는지 장기 패턴을 파악할 수 있다.
        """
        import datetime as _dt
        today_str = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        last_summary_date = getattr(self, "_last_daily_summary_date", None)
        if last_summary_date == today_str:
            return  # 오늘 이미 기록됨
        self._last_daily_summary_date = today_str

        # 섀도 포트폴리오 평가 결과 가져오기 (최신 캐시 사용)
        variant_report = getattr(self._demo_rule_variant_shadow_tester, "_last_report", None)
        if variant_report is None:
            return
        results = variant_report.get("results", [])
        if not results:
            return

        self._learning_service.record(
            LearningEvent(
                event_name="rule_performance_daily_summary",
                market=self._market,
                mode=self._trading_mode,
                payload={
                    "summary_date": today_str,
                    "leader_key": variant_report.get("leader_key"),
                    "is_fallback_leader": variant_report.get("is_fallback_leader", False),
                    "selection_type": variant_report.get("selection_type"),
                    "market_state": variant_report.get("market_state"),
                    "variants": [
                        {
                            "key": r.get("variant_key"),
                            "label": r.get("variant_label"),
                            "profit_rate": r.get("profit_rate"),
                            "realized_pnl": r.get("realized_pnl"),
                            "trade_count": r.get("trade_count"),
                            "stop_loss_count": r.get("stop_loss_count"),
                            "stop_loss_rate": r.get("stop_loss_rate"),
                            "profit_factor": r.get("profit_factor"),
                            "max_drawdown_pct": r.get("max_drawdown_pct"),
                            "promotion_eligible": r.get("promotion_eligible"),
                        }
                        for r in results
                    ],
                },
            )
        )


    # ── 24시간 무거래 시 섀도 포트폴리오 자동 리셋 ─────────────────────────────────────

    # 무거래 리셋 트리거 시간 (시간 단위)
    NO_TRADE_AUTO_RESET_HOURS = 24

    def _check_no_trade_auto_reset(self, *, position_exists: bool) -> None:
        """포지션이 없고 24시간 이상 매수 체결이 없으면 섀도 포트폴리오를 자동 리셋한다.

        리셋 후 is_initial_start=True 상태가 되어 조기 승격 조건(min_trades=1)이 적용되므로
        다음 사이클에서 빠르게 가장 좋은 룰을 선발하여 매매를 재개한다.

        조건:
          1. 포지션 없음 (포지션 보유 중 리셋하면 청산 로직이 꼬일 수 있음)
          2. 마지막 매수 체결 이후 NO_TRADE_AUTO_RESET_HOURS(24h) 경과
          3. 마지막 리셋 이후 NO_TRADE_AUTO_RESET_HOURS(24h) 경과 (반복 리셋 방지)
        """
        if position_exists:
            return  # 포지션 보유 중에는 리셋 안 함

        now = self._clock()
        # timezone-aware 비교를 위해 통일
        try:
            last_filled = self._last_trade_filled_at
            last_reset = self._last_variant_reset_at
            # aware/naive 혼합 방지
            if last_filled.tzinfo is None:
                last_filled = last_filled.replace(tzinfo=__import__("datetime").timezone.utc)
            if last_reset.tzinfo is None:
                last_reset = last_reset.replace(tzinfo=__import__("datetime").timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=__import__("datetime").timezone.utc)
        except Exception:
            return

        hours_since_filled = (now - last_filled).total_seconds() / 3600
        hours_since_reset = (now - last_reset).total_seconds() / 3600

        if hours_since_filled < self.NO_TRADE_AUTO_RESET_HOURS:
            return  # 아직 24시간 미경과
        if hours_since_reset < self.NO_TRADE_AUTO_RESET_HOURS:
            return  # 최근에 이미 리셋했음

        # ── 리셋 실행 ──────────────────────────────────────────────────────────
        self._demo_rule_variant_shadow_tester.reset()
        self._last_variant_reset_at = now
        # _consecutive_entry_blocks도 리셋해 no_trade 릴렉스 카운터 초기화
        self._consecutive_entry_blocks = 0

        self._learning_service.record(
            LearningEvent(
                event_name="variant_shadow_auto_reset",
                market=self._market,
                mode=self._trading_mode,
                payload={
                    "reason": "no_trade_24h",
                    "hours_since_last_filled": round(hours_since_filled, 1),
                    "hours_since_last_reset": round(hours_since_reset, 1),
                    "reset_threshold_hours": self.NO_TRADE_AUTO_RESET_HOURS,
                    "triggered_at": now.isoformat(),
                },
            )
        )

    def _should_check_auto_rule_update(self) -> bool:
        now = int(self._clock().timestamp())
        if now - self._last_auto_rule_update_check_at < self._auto_rule_update_check_interval_sec:
            return False
        self._last_auto_rule_update_check_at = now
        return True

    def _external_context(self, *, record: bool = True) -> dict[str, object] | None:
        if self._external_context_provider is None:
            return None
        snapshot = self._external_context_provider.snapshot(
            market=self._market,
            trade_coin=self._market.split("-")[-1],
        )
        if not record:
            return snapshot
        if self._etf_context_change_monitor is not None:
            self._etf_context_change_monitor.observe(
                market=self._market,
                mode=self._trading_mode,
                context=snapshot,
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

    @staticmethod
    def _external_context_weight(external_context: dict[str, object] | None) -> float:
        if not isinstance(external_context, dict):
            return 1.0
        try:
            return max(min(float(external_context.get("learning_weight", 1.0)), 1.25), 0.75)
        except (TypeError, ValueError):
            return 1.0

    def _should_relax_weak_signal(self, decision) -> bool:
        if not self._config.no_trade_adaptive_enabled:
            return False
        if not self._config.allow_weak_no_trade_relax:
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

    def _initial_observation_warmup_decision(self) -> dict[str, object] | None:
        if not self._requires_initial_observation_warmup:
            return None
        required_samples = max(int(self._config.initial_observation_min_samples), 0)
        required_seconds = max(int(self._config.initial_observation_warmup_seconds), 0)
        if required_samples <= 0 and required_seconds <= 0:
            return None
        observed_samples = len(self._prices)
        started_at = self._first_observation_at or self._clock()
        observed_seconds = max(int((self._clock() - started_at).total_seconds()), 0)
        samples_ready = observed_samples >= required_samples
        time_ready = observed_seconds >= required_seconds
        if samples_ready and time_ready:
            return None
        return {
            "buy_amount": 0.0,
            "history_count": observed_samples,
            "required_history": self._config.min_history,
            "initial_history_count": self._initial_market_history_count,
            "initial_observation_samples": observed_samples,
            "initial_observation_required_samples": required_samples,
            "initial_observation_elapsed_seconds": observed_seconds,
            "initial_observation_required_seconds": required_seconds,
            "initial_observation_samples_ready": samples_ready,
            "initial_observation_time_ready": time_ready,
        }

    def _market_regime_payload(
        self,
        current_price: float | None = None,
        *,
        reference_change_pct: float | None = None,
    ) -> dict[str, object]:
        if current_price is None:
            snapshot = self._market_price_store.get(self._market)
            if snapshot is None or snapshot.price <= 0:
                return {}
            current_price = snapshot.price
        try:
            trend = self._classify_current_market_state(
                float(current_price),
                reference_change_pct=reference_change_pct,
            )
        except Exception:
            return {}
        return {
            "market_state": trend.market_state,
            "market_state_label": trend.market_state_label,
            "box_range_low": trend.box_range_low,
            "box_range_high": trend.box_range_high,
            "market_state_recent_change_pct": trend.recent_change_pct,
            "market_state_source": trend.source,
            "market_state_learning_sample_count": trend.learning_sample_count,
            "market_state_learning_confidence": trend.learning_confidence,
        }

    def _record_market_observation(self, snapshot: UpbitTickerSnapshot) -> None:
        price_window = list(self._prices)
        payload: dict[str, object] = {
            "recorded_at": self._clock().isoformat(),
            "market": self._market,
            "mode": self._trading_mode,
            "trade_price": snapshot.trade_price,
            "traded_value": self._traded_value(snapshot),
            "spread_bps": self._config.spread_bps,
            "orderbook_imbalance": self._orderbook_imbalance(),
            "liquidity_score": self._liquidity_score(),
            "regime_score": self._regime_score(),
            "history_count": len(self._prices),
            "price_window": price_window,
            "price_window_low": min(price_window) if price_window else None,
            "price_window_high": max(price_window) if price_window else None,
            "traded_value_window": list(self._traded_values),
        }
        payload.update(
            self._market_regime_payload(
                snapshot.trade_price,
                reference_change_pct=snapshot.signed_change_rate,
            ),
        )
        ticker_meta = asdict(snapshot)
        payload["ticker"] = {key: value for key, value in ticker_meta.items() if value is not None}
        record_observation = getattr(self._learning_service, "record_market_observation", None)
        if record_observation is not None:
            record_observation(payload)

    def _market_window_summary(self) -> dict[str, object]:
        prices = [float(price) for price in self._prices if price > 0]
        traded_values = [float(value) for value in self._traded_values if value >= 0]
        if len(prices) < 2:
            price_change_pct = 0.0
            last_return_pct = 0.0
            price_range_pct = 0.0
            price_window_low = prices[-1] if prices else None
            price_window_high = prices[-1] if prices else None
        else:
            price_window_low = min(prices)
            price_window_high = max(prices)
            price_change_pct = round((prices[-1] - prices[0]) / prices[0], 6)
            last_return_pct = round((prices[-1] - prices[-2]) / prices[-2], 6)
            price_range_pct = round((price_window_high - price_window_low) / prices[-1], 6)
        if len(traded_values) < 2:
            traded_value_multiple = 1.0
        else:
            baseline = sum(traded_values[:-1]) / max(len(traded_values[:-1]), 1)
            traded_value_multiple = round(traded_values[-1] / baseline, 4) if baseline > 0 else 1.0
        return {
            "sample_count": len(prices),
            "current_price": prices[-1] if prices else None,
            "price_change_pct": price_change_pct,
            "last_return_pct": last_return_pct,
            "price_range_pct": price_range_pct,
            "price_window_low": price_window_low,
            "price_window_high": price_window_high,
            "traded_value_multiple": traded_value_multiple,
            "spread_bps": self._config.spread_bps,
            "orderbook_imbalance": self._orderbook_imbalance(),
            "liquidity_score": self._liquidity_score(),
            "regime_score": self._regime_score(),
        }
