from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from app.integrations.telegram.notifier import TelegramNotifier
from app.services.execution.demo import FillResult, OrderIntent
from app.services.execution.ledger import ExecutionLedger
from app.services.execution.rules import UpbitOrderRules
from app.services.learning.service import LearningEvent, LearningService
from app.services.portfolio.sync import PortfolioState
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator


class RegularSellExecutor:
    """Execute non-stop-loss sell orders."""

    def __init__(self, *, executor: Any) -> None:
        self._executor = executor

    def execute(self, *, market: str, price: float, quantity: float) -> Any:
        return self._executor.execute(
            OrderIntent(
                market=market,
                side="sell",
                price=price,
                quantity=quantity,
                order_type="market",
                is_stop_loss=False,
            ),
        )


class StopLossSellExecutor:
    """Execute sell orders that must be tracked as stop-loss exits."""

    def __init__(self, *, executor: Any) -> None:
        self._executor = executor

    def execute(self, *, market: str, price: float, quantity: float) -> Any:
        return self._executor.execute(
            OrderIntent(
                market=market,
                side="sell",
                price=price,
                quantity=quantity,
                order_type="market",
                is_stop_loss=True,
            ),
        )


class PositionExitService:
    """Evaluate active position exits and execute them against the current executor."""

    def __init__(
        self,
        *,
        position_store: CurrentPositionStore,
        hard_stop_monitor: HardStopMonitor,
        post_entry_validator: PostEntryValidator,
        executor: Any,
        trading_mode: str,
        learning_service: LearningService | None = None,
        telegram_notifier: TelegramNotifier | None = None,
        execution_ledger: ExecutionLedger | None = None,
        initial_portfolio_state: PortfolioState | None = None,
        position_lifecycle_ledger: PositionLifecycleLedger | None = None,
        min_order_amount_krw: float = 5_000.0,
        order_rules: UpbitOrderRules | None = None,
    ) -> None:
        self._position_store = position_store
        self._hard_stop_monitor = hard_stop_monitor
        self._post_entry_validator = post_entry_validator
        self._executor = executor
        self._stop_loss_sell_executor = StopLossSellExecutor(executor=executor)
        self._trading_mode = trading_mode
        self._learning_service = learning_service
        self._telegram_notifier = telegram_notifier
        self._execution_ledger = execution_ledger
        self._initial_portfolio_state = initial_portfolio_state
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._order_rules = order_rules or UpbitOrderRules(
            min_order_amount_krw=min_order_amount_krw,
        )

    def evaluate_and_execute(
        self,
        *,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> dict[str, object]:
        position = self._position_store.get()
        if position is None:
            return {
                "status": "empty",
                "position": None,
                "trigger": None,
                "execution": None,
            }

        hard_stop = self._hard_stop_monitor.evaluate(
            position=position,
            current_price=current_price,
        )
        if hard_stop.triggered:
            if not self._order_rules.is_allowed(
                market=position.market,
                price=hard_stop.trigger_price,
                quantity=hard_stop.quantity,
            ):
                self._record_exit_blocked(
                    position=position,
                    reason_code=hard_stop.reason_code,
                    blocked_reason="MIN_ORDER_AMOUNT_SELL",
                    current_price=current_price,
                    elapsed_sec=elapsed_sec,
                    momentum_score=momentum_score,
                    orderbook_imbalance=orderbook_imbalance,
                )
                return {
                    "status": "blocked",
                    "position": self._position_store.to_payload(position),
                    "trigger": {
                        "type": "hard_stop",
                        "reason_code": hard_stop.reason_code,
                        "exit_ratio": 0.0,
                        "blocked_reason": "MIN_ORDER_AMOUNT_SELL",
                    },
                    "execution": None,
                }
            execution = self._stop_loss_sell_executor.execute(
                market=position.market,
                price=hard_stop.trigger_price,
                quantity=hard_stop.quantity,
            )
            self._position_store.clear()
            self._record_exit_event(
                position=position,
                trigger_type="hard_stop",
                reason_code=hard_stop.reason_code,
                exit_ratio=1.0,
                current_price=current_price,
                elapsed_sec=elapsed_sec,
                momentum_score=momentum_score,
                orderbook_imbalance=orderbook_imbalance,
                execution=execution,
                remaining_quantity=0.0,
            )
            return {
                "status": "ok",
                "position": None,
                "trigger": {
                    "type": "hard_stop",
                    "reason_code": hard_stop.reason_code,
                    "exit_ratio": 1.0,
                },
                "execution": None if execution is None else asdict(execution),
            }

        post_entry = self._post_entry_validator.evaluate(
            position=position,
            current_price=current_price,
            elapsed_sec=elapsed_sec,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        if not post_entry.triggered:
            return {
                "status": "ok",
                "position": self._position_store.to_payload(position),
                "trigger": None,
                "execution": None,
            }

        dynamic_exit_ratio = self._dynamic_exit_ratio(
            requested_exit_ratio=post_entry.exit_ratio,
            reason_code=post_entry.reason_code,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        resolved_exit = self._resolve_exit_quantity(
            position=position,
            current_price=current_price,
            requested_exit_ratio=dynamic_exit_ratio,
        )
        if resolved_exit["blocked_reason"] is not None:
            self._record_exit_blocked(
                position=position,
                reason_code=post_entry.reason_code,
                blocked_reason=resolved_exit["blocked_reason"],
                current_price=current_price,
                elapsed_sec=elapsed_sec,
                momentum_score=momentum_score,
                orderbook_imbalance=orderbook_imbalance,
            )
            return {
                "status": "blocked",
                "position": self._position_store.to_payload(position),
                "trigger": {
                    "type": "post_entry",
                    "reason_code": post_entry.reason_code,
                    "exit_ratio": 0.0,
                    "blocked_reason": resolved_exit["blocked_reason"],
                },
                "execution": None,
            }

        exit_quantity = resolved_exit["quantity"]
        exit_ratio = resolved_exit["exit_ratio"]
        is_take_profit = post_entry.reason_code == "TAKE_PROFIT_TARGET_HIT"
        sell_executor = (
            RegularSellExecutor(executor=self._executor)
            if is_take_profit
            else self._stop_loss_sell_executor
        )
        execution = sell_executor.execute(
            market=position.market,
            price=current_price,
            quantity=exit_quantity,
        )
        remaining_quantity = round(position.quantity - exit_quantity, 8)
        if remaining_quantity <= 0:
            self._position_store.clear()
            updated_position = None
        else:
            updated_position = replace(position, quantity=remaining_quantity)
            self._position_store.save(updated_position)
        self._record_exit_event(
            position=position,
            trigger_type="take_profit" if is_take_profit else "post_entry",
            reason_code=post_entry.reason_code,
            exit_ratio=exit_ratio,
            current_price=current_price,
            elapsed_sec=elapsed_sec,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
            execution=execution,
            remaining_quantity=remaining_quantity,
        )

        return {
            "status": "ok",
            "position": None if updated_position is None else self._position_store.to_payload(updated_position),
            "trigger": {
                "type": "take_profit" if is_take_profit else "post_entry",
                "reason_code": post_entry.reason_code,
                "exit_ratio": exit_ratio,
            },
            "execution": None if execution is None else asdict(execution),
        }

    def _resolve_exit_quantity(
        self,
        *,
        position,
        current_price: float,
        requested_exit_ratio: float,
    ) -> dict[str, Any]:
        full_amount = self._order_rules.notional(price=current_price, quantity=position.quantity)
        if full_amount < self._order_rules.min_order_amount_krw:
            return {
                "quantity": 0.0,
                "exit_ratio": 0.0,
                "blocked_reason": "MIN_ORDER_AMOUNT_SELL",
            }

        requested_quantity = round(position.quantity * requested_exit_ratio, 8)
        requested_amount = self._order_rules.notional(price=current_price, quantity=requested_quantity)
        remaining_quantity = round(position.quantity - requested_quantity, 8)
        remaining_amount = self._order_rules.notional(price=current_price, quantity=remaining_quantity)
        if (
            requested_amount < self._order_rules.min_order_amount_krw
            or (remaining_quantity > 0 and remaining_amount < self._order_rules.min_order_amount_krw)
        ):
            return {
                "quantity": position.quantity,
                "exit_ratio": 1.0,
                "blocked_reason": None,
            }

        return {
            "quantity": requested_quantity,
            "exit_ratio": requested_exit_ratio,
            "blocked_reason": None,
        }

    @staticmethod
    def _dynamic_exit_ratio(
        *,
        requested_exit_ratio: float,
        reason_code: str | None,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> float:
        if reason_code == "TAKE_PROFIT_TARGET_HIT":
            if momentum_score > 0.65 and orderbook_imbalance > 0:
                return min(requested_exit_ratio, 0.5)
            if momentum_score < 0.1 or orderbook_imbalance < -0.15:
                return 1.0
            return requested_exit_ratio
        if momentum_score < -0.3 or orderbook_imbalance < -0.3:
            return 1.0
        return max(min(requested_exit_ratio, 1.0), 0.25)

    def _record_exit_blocked(
        self,
        *,
        position,
        reason_code: str | None,
        blocked_reason: str,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
    ) -> None:
        if self._learning_service is None:
            return
        self._learning_service.record(
            LearningEvent(
                event_name="position_exit_blocked",
                market=position.market,
                mode=self._trading_mode,
                payload={
                    "reason_code": reason_code,
                    "blocked_reason": blocked_reason,
                    "current_price": current_price,
                    "elapsed_sec": elapsed_sec,
                    "momentum_score": momentum_score,
                    "orderbook_imbalance": orderbook_imbalance,
                    "entry_price": position.entry_price,
                    "quantity": position.quantity,
                    "notional": self._order_rules.notional(price=current_price, quantity=position.quantity),
                    "min_order_amount_krw": self._order_rules.min_order_amount_krw,
                },
            ),
        )

    def _record_exit_event(
        self,
        *,
        position,
        trigger_type: str,
        reason_code: str | None,
        exit_ratio: float,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
        execution: Any,
        remaining_quantity: float,
    ) -> None:
        if self._learning_service is not None:
            self._learning_service.record(
                LearningEvent(
                    event_name="position_exit_completed",
                    market=position.market,
                    mode=getattr(execution, "mode", self._trading_mode),
                    payload={
                        "trigger_type": trigger_type,
                        "reason_code": reason_code,
                        "exit_ratio": exit_ratio,
                        "sell_split_enabled": exit_ratio < 1.0,
                        "current_price": current_price,
                        "elapsed_sec": elapsed_sec,
                        "momentum_score": momentum_score,
                        "orderbook_imbalance": orderbook_imbalance,
                        "entry_price": position.entry_price,
                        "previous_quantity": position.quantity,
                        "remaining_quantity": max(remaining_quantity, 0.0),
                        "execution_status": getattr(execution, "status", None),
                        "is_stop_loss": getattr(execution, "is_stop_loss", True),
                    },
                ),
            )
            self._learning_service.record(
                LearningEvent(
                    event_name="position_lifecycle_updated",
                    market=position.market,
                    mode=getattr(execution, "mode", self._trading_mode),
                    payload={
                        "event_type": "closed" if max(remaining_quantity, 0.0) <= 0 else "reduced",
                        "reason_code": reason_code,
                        "signal_level": position.signal_level,
                        "entry_price": position.entry_price,
                        "previous_quantity": position.quantity,
                        "remaining_quantity": max(remaining_quantity, 0.0),
                        "stop_loss_price": position.stop_loss_price,
                    },
                ),
            )
        if self._execution_ledger is not None and isinstance(execution, FillResult):
            self._execution_ledger.record_fill(execution, reason_code=reason_code)
        if self._position_lifecycle_ledger is not None:
            if max(remaining_quantity, 0.0) <= 0:
                lifecycle_position = position
                event_type = "closed"
            else:
                lifecycle_position = replace(position, quantity=max(remaining_quantity, 0.0))
                event_type = "reduced"
            self._position_lifecycle_ledger.record(
                event_type=event_type,
                position=lifecycle_position,
                reason_code=reason_code,
            )
        if self._telegram_notifier is not None and hasattr(execution, "filled_price"):
            total_asset_value = self._total_asset_value_after_fill(
                current_price=execution.filled_price,
            )
            self._telegram_notifier.notify_fill(
                execution,
                reason_code=reason_code,
                entry_price=position.entry_price,
                total_asset_value=total_asset_value,
            )

    def _total_asset_value_after_fill(self, *, current_price: float) -> float | None:
        if self._execution_ledger is None or self._initial_portfolio_state is None:
            return None
        portfolio = self._execution_ledger.portfolio_state(
            initial_cash=self._initial_portfolio_state.cash_balance,
            asset_currency=self._initial_portfolio_state.asset_currency,
        )
        return round(portfolio.cash_balance + (portfolio.asset_balance * current_price), 2)
