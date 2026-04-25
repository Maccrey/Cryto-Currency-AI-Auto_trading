from __future__ import annotations

from typing import Any

from app.services.execution.demo import DemoExecutor
from app.services.execution.interface import ExecutionExecutor
from app.services.execution.live import LiveExecutor


class ExecutionFactory:
    """Create mode-appropriate execution services."""

    def __init__(self, *, live_order_gateway: Any, learning_service: Any | None = None) -> None:
        self._live_order_gateway = live_order_gateway
        self._learning_service = learning_service

    def create(self, *, trading_mode: str, safe_mode: bool, hard_stop: bool = False) -> ExecutionExecutor:
        if trading_mode == "live":
            return LiveExecutor(
                live_order_gateway=self._live_order_gateway,
                trading_mode=trading_mode,
                safe_mode=safe_mode,
                hard_stop=hard_stop,
            )

        return DemoExecutor(
            live_order_gateway=self._live_order_gateway,
            learning_service=self._learning_service,
        )
