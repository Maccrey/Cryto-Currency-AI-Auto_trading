from __future__ import annotations

from typing import Any
from pathlib import Path

from app.services.execution.demo import DemoExecutor
from app.services.execution.interface import ExecutionExecutor
from app.services.execution.live import LiveExecutor
from app.services.execution.rules import UpbitOrderRules


class ExecutionFactory:
    """Create mode-appropriate execution services."""

    def __init__(
        self,
        *,
        live_order_gateway: Any,
        learning_service: Any | None = None,
        fee_rate: float = DemoExecutor.FEE_RATE,
        min_order_amount_krw: float = 5_000.0,
        order_rules: UpbitOrderRules | None = None,
        journal_path: Path | None = None,
    ) -> None:
        self._live_order_gateway = live_order_gateway
        self._learning_service = learning_service
        self._fee_rate = fee_rate
        self._journal_path = journal_path
        self._order_rules = order_rules or UpbitOrderRules(
            min_order_amount_krw=min_order_amount_krw,
        )

    def create(self, *, trading_mode: str, safe_mode: bool, hard_stop: bool = False) -> ExecutionExecutor:
        if trading_mode == "live":
            return LiveExecutor(
                live_order_gateway=self._live_order_gateway,
                trading_mode=trading_mode,
                safe_mode=safe_mode,
                hard_stop=hard_stop,
                order_rules=self._order_rules,
                journal_path=self._journal_path,
            )

        return DemoExecutor(
            live_order_gateway=self._live_order_gateway,
            learning_service=self._learning_service,
            fee_rate=self._fee_rate,
        )
