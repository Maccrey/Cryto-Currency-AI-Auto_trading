from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from app.integrations.telegram.notifier import TelegramNotifier
from app.services.execution.demo import OrderIntent
from app.services.learning.service import LearningEvent, LearningService
from app.services.position.store import CurrentPositionStore
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator


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
    ) -> None:
        self._position_store = position_store
        self._hard_stop_monitor = hard_stop_monitor
        self._post_entry_validator = post_entry_validator
        self._executor = executor
        self._trading_mode = trading_mode
        self._learning_service = learning_service
        self._telegram_notifier = telegram_notifier

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
            execution = self._executor.execute(
                OrderIntent(
                    market=position.market,
                    side=hard_stop.order_side,
                    price=hard_stop.trigger_price,
                    quantity=hard_stop.quantity,
                    order_type="market",
                    is_stop_loss=True,
                ),
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

        exit_quantity = round(position.quantity * post_entry.exit_ratio, 8)
        execution = self._executor.execute(
            OrderIntent(
                market=position.market,
                side=post_entry.order_side,
                price=current_price,
                quantity=exit_quantity,
                order_type="market",
                is_stop_loss=True,
            ),
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
            trigger_type="post_entry",
            reason_code=post_entry.reason_code,
            exit_ratio=post_entry.exit_ratio,
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
                "type": "post_entry",
                "reason_code": post_entry.reason_code,
                "exit_ratio": post_entry.exit_ratio,
            },
            "execution": None if execution is None else asdict(execution),
        }

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
        if self._telegram_notifier is not None and hasattr(execution, "filled_price"):
            self._telegram_notifier.notify_fill(execution)
