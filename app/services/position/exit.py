from __future__ import annotations

from collections.abc import Callable
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
        initial_portfolio_state_provider: Callable[[], PortfolioState | None] | None = None,
        position_lifecycle_ledger: PositionLifecycleLedger | None = None,
        min_order_amount_krw: float = 5_000.0,
        order_rules: UpbitOrderRules | None = None,
        trading_fee_rate: float = 0.0005,
        take_profit_min_net_pct: float = 0.005,
        box_range_min_net_profit_pct: float = 0.004,
        box_range_edge_zone_ratio: float = 0.25,
        take_profit_min_exit_ratio: float = 0.75,
        weak_signal_take_profit_min_exit_ratio: float = 1.0,
        profit_protection_buffer_pct: float = 0.0002,
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
        self._initial_portfolio_state_provider = initial_portfolio_state_provider
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._order_rules = order_rules or UpbitOrderRules(
            min_order_amount_krw=min_order_amount_krw,
        )
        self._trading_fee_rate = max(float(trading_fee_rate), 0.0)
        self._take_profit_min_net_pct = max(float(take_profit_min_net_pct), 0.0)
        self._box_range_min_net_profit_pct = max(float(box_range_min_net_profit_pct), self._trading_fee_rate * 2)
        self._box_range_edge_zone_ratio = min(max(float(box_range_edge_zone_ratio), 0.05), 0.5)
        self._take_profit_min_exit_ratio = min(max(float(take_profit_min_exit_ratio), 0.25), 1.0)
        self._weak_signal_take_profit_min_exit_ratio = min(max(float(weak_signal_take_profit_min_exit_ratio), self._take_profit_min_exit_ratio), 1.0)
        self._profit_protection_buffer_pct = max(float(profit_protection_buffer_pct), 0.0)

    def evaluate_and_execute(
        self,
        *,
        current_price: float,
        elapsed_sec: int,
        momentum_score: float,
        orderbook_imbalance: float,
        market_state: str | None = None,
        box_range_low: float | None = None,
        box_range_high: float | None = None,
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
                    market_state=market_state,
                    box_range_low=box_range_low,
                    box_range_high=box_range_high,
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
            self._post_entry_validator.reset()   # 트레일링 스탑 상태 초기화
            self._record_exit_event(
                position=position,
                trigger_type="hard_stop",
                reason_code=hard_stop.reason_code,
                exit_ratio=1.0,
                current_price=current_price,
                elapsed_sec=elapsed_sec,
                momentum_score=momentum_score,
                orderbook_imbalance=orderbook_imbalance,
                market_state=market_state,
                box_range_low=box_range_low,
                box_range_high=box_range_high,
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

        box_range_exit = self._box_range_exit(
            position=position,
            current_price=current_price,
            market_state=market_state,
            box_range_low=box_range_low,
            box_range_high=box_range_high,
        )
        if box_range_exit["triggered"]:
            resolved_exit = self._resolve_exit_quantity(
                position=position,
                current_price=current_price,
                requested_exit_ratio=1.0,
            )
            if resolved_exit["blocked_reason"] is not None:
                self._record_exit_blocked(
                    position=position,
                    reason_code="BOX_RANGE_HIGH_TAKE_PROFIT",
                    blocked_reason=resolved_exit["blocked_reason"],
                    current_price=current_price,
                    elapsed_sec=elapsed_sec,
                    momentum_score=momentum_score,
                    orderbook_imbalance=orderbook_imbalance,
                    market_state=market_state,
                    box_range_low=box_range_low,
                    box_range_high=box_range_high,
                )
                return {
                    "status": "blocked",
                    "position": self._position_store.to_payload(position),
                    "trigger": {
                        "type": "box_range_take_profit",
                        "reason_code": "BOX_RANGE_HIGH_TAKE_PROFIT",
                        "exit_ratio": 0.0,
                        "blocked_reason": resolved_exit["blocked_reason"],
                    },
                    "execution": None,
                }
            exit_quantity = resolved_exit["quantity"]
            execution = RegularSellExecutor(executor=self._executor).execute(
                market=position.market,
                price=current_price,
                quantity=exit_quantity,
            )
            self._position_store.clear()
            self._post_entry_validator.reset()   # 트레일링 스탑 상태 초기화
            self._record_exit_event(
                position=position,
                trigger_type="box_range_take_profit",
                reason_code="BOX_RANGE_HIGH_TAKE_PROFIT",
                exit_ratio=1.0,
                current_price=current_price,
                elapsed_sec=elapsed_sec,
                momentum_score=momentum_score,
                orderbook_imbalance=orderbook_imbalance,
                market_state=market_state,
                box_range_low=box_range_low,
                box_range_high=box_range_high,
                execution=execution,
                remaining_quantity=0.0,
            )
            return {
                "status": "ok",
                "position": None,
                "trigger": {
                    "type": "box_range_take_profit",
                    "reason_code": "BOX_RANGE_HIGH_TAKE_PROFIT",
                    "exit_ratio": 1.0,
                    "box_range_low": box_range_exit["box_range_low"],
                    "box_range_high": box_range_exit["box_range_high"],
                },
                "execution": None if execution is None else asdict(execution),
            }

        take_profit_exit = self._take_profit_exit(
            position=position,
            current_price=current_price,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
            market_state=market_state,
        )
        if take_profit_exit["triggered"]:
            take_profit_details = {key: value for key, value in take_profit_exit.items() if key != "triggered"}
            resolved_exit = self._resolve_exit_quantity(
                position=position,
                current_price=current_price,
                requested_exit_ratio=self._dynamic_exit_ratio(
                    requested_exit_ratio=1.0,
                    reason_code="TAKE_PROFIT_TARGET_HIT",
                    momentum_score=momentum_score,
                    orderbook_imbalance=orderbook_imbalance,
                    signal_level=position.signal_level,
                    take_profit_min_exit_ratio=self._take_profit_min_exit_ratio,
                    weak_signal_take_profit_min_exit_ratio=self._weak_signal_take_profit_min_exit_ratio,
                ),
            )
            if resolved_exit["blocked_reason"] is not None:
                self._record_exit_blocked(
                    position=position,
                    reason_code="TAKE_PROFIT_TARGET_HIT",
                    blocked_reason=resolved_exit["blocked_reason"],
                    current_price=current_price,
                    elapsed_sec=elapsed_sec,
                    momentum_score=momentum_score,
                    orderbook_imbalance=orderbook_imbalance,
                    market_state=market_state,
                    box_range_low=box_range_low,
                    box_range_high=box_range_high,
                )
                return {
                    "status": "blocked",
                    "position": self._position_store.to_payload(position),
                    "trigger": {
                        "type": "take_profit",
                        "reason_code": "TAKE_PROFIT_TARGET_HIT",
                        "exit_ratio": 0.0,
                        "blocked_reason": resolved_exit["blocked_reason"],
                        **take_profit_details,
                    },
                    "execution": None,
                }
            exit_quantity = resolved_exit["quantity"]
            exit_ratio = resolved_exit["exit_ratio"]
            execution = RegularSellExecutor(executor=self._executor).execute(
                market=position.market,
                price=current_price,
                quantity=exit_quantity,
            )
            remaining_quantity = round(position.quantity - exit_quantity, 8)
            if remaining_quantity <= 0:
                self._position_store.clear()
                self._post_entry_validator.reset()   # 트레일링 스탑 상태 초기화
                updated_position = None
            else:
                updated_position = self._profit_protected_position(
                    position=position,
                    current_price=current_price,
                    remaining_quantity=remaining_quantity,
                )
                self._position_store.save(updated_position)
            self._record_exit_event(
                position=position,
                trigger_type="take_profit",
                reason_code="TAKE_PROFIT_TARGET_HIT",
                exit_ratio=exit_ratio,
                current_price=current_price,
                elapsed_sec=elapsed_sec,
                momentum_score=momentum_score,
                orderbook_imbalance=orderbook_imbalance,
                market_state=market_state,
                box_range_low=box_range_low,
                box_range_high=box_range_high,
                execution=execution,
                remaining_quantity=remaining_quantity,
                extra_payload=take_profit_details,
            )
            return {
                "status": "ok",
                "position": None if updated_position is None else self._position_store.to_payload(updated_position),
                "trigger": {
                    "type": "take_profit",
                    "reason_code": "TAKE_PROFIT_TARGET_HIT",
                    "exit_ratio": exit_ratio,
                    **take_profit_details,
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
        if post_entry.triggered and post_entry.reason_code == "TAKE_PROFIT_TARGET_HIT":
            return {
                "status": "ok",
                "position": self._position_store.to_payload(position),
                "trigger": None,
                "execution": None,
            }
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
            signal_level=position.signal_level,
            take_profit_min_exit_ratio=self._take_profit_min_exit_ratio,
            weak_signal_take_profit_min_exit_ratio=self._weak_signal_take_profit_min_exit_ratio,
        )
        if self._should_full_exit_post_entry_stop(
            position=position,
            reason_code=post_entry.reason_code,
        ):
            dynamic_exit_ratio = 1.0
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
                market_state=market_state,
                box_range_low=box_range_low,
                box_range_high=box_range_high,
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
        # 추적청산은 손실 방어 규칙이지만, 수수료를 넘긴 수익 구간에서만
        # 발동하도록 PostEntryValidator가 보장한다. 손절 주문으로 기록하면
        # 손절 통계와 A~R 평가가 왜곡되므로 일반 매도로 분류한다.
        is_take_profit = post_entry.reason_code in {
            "TAKE_PROFIT_TARGET_HIT",
            "TRAILING_STOP_TRIGGERED",
        }
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
            self._post_entry_validator.reset()   # 트레일링 스탑 상태 초기화
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
            market_state=market_state,
            box_range_low=box_range_low,
            box_range_high=box_range_high,
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

    def _box_range_exit(
        self,
        *,
        position,
        current_price: float,
        market_state: str | None,
        box_range_low: float | None,
        box_range_high: float | None,
    ) -> dict[str, object]:
        if market_state != "box" or box_range_low is None or box_range_high is None:
            return {"triggered": False}
        if current_price <= 0 or box_range_low <= 0 or box_range_high <= box_range_low:
            return {"triggered": False}
        box_width = box_range_high - box_range_low
        box_width_pct = box_width / box_range_low
        min_required_pct = (self._trading_fee_rate * 2) + self._box_range_min_net_profit_pct
        if box_width_pct < min_required_pct:
            return {"triggered": False}
        high_zone_start = box_range_high - (box_width * self._box_range_edge_zone_ratio)
        min_exit_price = position.entry_price * (1 + min_required_pct)
        if current_price < high_zone_start or current_price < min_exit_price:
            return {"triggered": False}
        return {
            "triggered": True,
            "box_range_low": box_range_low,
            "box_range_high": box_range_high,
            "box_width_pct": round(box_width_pct, 6),
        }

    def _take_profit_exit(
        self,
        *,
        position,
        current_price: float,
        momentum_score: float,
        orderbook_imbalance: float,
        market_state: str | None,
    ) -> dict[str, object]:
        if position.entry_price <= 0 or current_price <= 0:
            return {"triggered": False}
        gross_return_pct = (current_price - position.entry_price) / position.entry_price
        round_trip_fee_pct = self._trading_fee_rate * 2
        net_return_pct = gross_return_pct - round_trip_fee_pct
        target_pct = self._dynamic_take_profit_target_pct(
            base_target_pct=position.min_expected_return_pct,
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
            market_state=market_state,
        )
        if gross_return_pct < target_pct or net_return_pct < self._take_profit_min_net_pct:
            return {"triggered": False}
        return {
            "triggered": True,
            "take_profit_target_pct": round(target_pct, 6),
            "unrealized_return_pct": round(gross_return_pct, 6),
            "estimated_net_return_pct": round(net_return_pct, 6),
            "round_trip_fee_pct": round(round_trip_fee_pct, 6),
        }

    def _dynamic_take_profit_target_pct(
        self,
        *,
        base_target_pct: float,
        momentum_score: float,
        orderbook_imbalance: float,
        market_state: str | None,
    ) -> float:
        continuation_score = self._chart_continuation_score(
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        market_adjustment = {
            "bull": 0.12,
            "box": -0.05,
            "bear": -0.18,
        }.get(str(market_state or ""), 0.0)
        strength_multiplier = min(max(0.72 + (continuation_score * 0.88) + market_adjustment, 0.65), 1.75)
        dynamic_target_pct = max(float(base_target_pct), 0.0) * strength_multiplier
        fee_adjusted_floor = (self._trading_fee_rate * 2) + self._take_profit_min_net_pct
        return round(max(dynamic_target_pct, fee_adjusted_floor), 6)

    @staticmethod
    def _dynamic_exit_ratio(
        *,
        requested_exit_ratio: float,
        reason_code: str | None,
        momentum_score: float,
        orderbook_imbalance: float,
        signal_level: str | None = None,
        take_profit_min_exit_ratio: float = 0.75,
        weak_signal_take_profit_min_exit_ratio: float = 1.0,
    ) -> float:
        continuation_score = PositionExitService._chart_continuation_score(
            momentum_score=momentum_score,
            orderbook_imbalance=orderbook_imbalance,
        )
        inverse_chart_exit_ratio = round(0.25 + ((1.0 - continuation_score) * 0.75), 3)
        if reason_code == "TAKE_PROFIT_TARGET_HIT":
            if momentum_score < -0.3 or orderbook_imbalance < -0.3:
                return 1.0
            min_exit_ratio = weak_signal_take_profit_min_exit_ratio if signal_level == "weak" else take_profit_min_exit_ratio
            return min(max(inverse_chart_exit_ratio, min_exit_ratio), requested_exit_ratio)
        if momentum_score < -0.3 or orderbook_imbalance < -0.3:
            return 1.0
        return max(min(requested_exit_ratio, 1.0), inverse_chart_exit_ratio, 0.25)

    @staticmethod
    def _should_full_exit_post_entry_stop(
        *,
        position,
        reason_code: str | None,
    ) -> bool:
        return str(reason_code or "").startswith("STOP_LOSS_")

    def _profit_protected_position(
        self,
        *,
        position,
        current_price: float,
        remaining_quantity: float,
    ):
        fee_adjusted_floor = position.entry_price * (
            1 + (self._trading_fee_rate * 2) + self._profit_protection_buffer_pct
        )
        if fee_adjusted_floor > current_price:
            protected_stop_loss_price = position.stop_loss_price
        else:
            protected_stop_loss_price = max(
                position.stop_loss_price,
                min(fee_adjusted_floor, current_price * (1 - self._trading_fee_rate)),
            )
        return replace(
            position,
            quantity=remaining_quantity,
            stop_loss_price=round(protected_stop_loss_price, 2),
            stop_loss_reason="PROFIT_PROTECTED",
        )

    @staticmethod
    def _market_state_payload(
        *,
        market_state: str | None,
        box_range_low: float | None,
        box_range_high: float | None,
    ) -> dict[str, object]:
        if market_state not in {"bull", "bear", "box"}:
            return {}
        return {
            "market_state": market_state,
            "market_state_label": {
                "bull": "상승장",
                "bear": "하락장",
                "box": "박스권",
            }[market_state],
            "box_range_low": box_range_low if market_state == "box" else None,
            "box_range_high": box_range_high if market_state == "box" else None,
        }

    @staticmethod
    def _return_pct(*, entry_price: float, current_price: float) -> float:
        if entry_price <= 0 or current_price <= 0:
            return 0.0
        return round((current_price - entry_price) / entry_price, 6)

    @staticmethod
    def _chart_continuation_score(*, momentum_score: float, orderbook_imbalance: float) -> float:
        normalized_momentum = (max(min(momentum_score, 1.0), -1.0) + 1.0) / 2.0
        normalized_imbalance = max(min(orderbook_imbalance + 0.5, 1.0), 0.0)
        return max(min((normalized_momentum * 0.7) + (normalized_imbalance * 0.3), 1.0), 0.0)

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
        market_state: str | None = None,
        box_range_low: float | None = None,
        box_range_high: float | None = None,
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
                    **self._market_state_payload(
                        market_state=market_state,
                        box_range_low=box_range_low,
                        box_range_high=box_range_high,
                    ),
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
        extra_payload: dict[str, object] | None = None,
        market_state: str | None = None,
        box_range_low: float | None = None,
        box_range_high: float | None = None,
    ) -> None:
        extra_payload = extra_payload or {}
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
                        "unrealized_return_pct": self._return_pct(
                            entry_price=position.entry_price,
                            current_price=current_price,
                        ),
                        **self._market_state_payload(
                            market_state=market_state,
                            box_range_low=box_range_low,
                            box_range_high=box_range_high,
                        ),
                        "entry_price": position.entry_price,
                        "previous_quantity": position.quantity,
                        "remaining_quantity": max(remaining_quantity, 0.0),
                        "execution_status": getattr(execution, "status", None),
                        "is_stop_loss": getattr(execution, "is_stop_loss", True),
                        **extra_payload,
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
                        **self._market_state_payload(
                            market_state=market_state,
                            box_range_low=box_range_low,
                            box_range_high=box_range_high,
                        ),
                    },
                ),
            )
        if self._execution_ledger is not None and isinstance(execution, FillResult):
            self._execution_ledger.record_fill(
                execution,
                reason_code=reason_code,
                signal_level=position.signal_level,
                market_state=market_state,
                market_state_label=self._market_state_payload(
                    market_state=market_state,
                    box_range_low=box_range_low,
                    box_range_high=box_range_high,
                ).get("market_state_label"),
                box_range_low=box_range_low if market_state == "box" else None,
                box_range_high=box_range_high if market_state == "box" else None,
            )
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
            market_payload = self._market_state_payload(
                market_state=market_state,
                box_range_low=box_range_low,
                box_range_high=box_range_high,
            )
            self._telegram_notifier.notify_fill(
                execution,
                reason_code=reason_code,
                entry_price=position.entry_price,
                total_asset_value=total_asset_value,
                market_state_label=market_payload.get("market_state_label"),
                box_range_low=market_payload.get("box_range_low"),
                box_range_high=market_payload.get("box_range_high"),
            )

    def _total_asset_value_after_fill(self, *, current_price: float) -> float | None:
        initial_portfolio_state = self._current_initial_portfolio_state()
        if self._execution_ledger is None or initial_portfolio_state is None:
            return None
        portfolio = self._execution_ledger.portfolio_state(
            initial_cash=initial_portfolio_state.cash_balance,
            asset_currency=initial_portfolio_state.asset_currency,
        )
        return round(portfolio.cash_balance + (portfolio.asset_balance * current_price), 2)

    def _current_initial_portfolio_state(self) -> PortfolioState | None:
        if self._initial_portfolio_state_provider is not None:
            return self._initial_portfolio_state_provider()
        return self._initial_portfolio_state
