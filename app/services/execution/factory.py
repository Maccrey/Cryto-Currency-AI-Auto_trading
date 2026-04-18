from __future__ import annotations

from typing import Any

from app.services.execution.demo import DemoExecutor
from app.services.execution.live import LiveExecutor


class ExecutionFactory:
    """Create mode-appropriate execution services."""

    def __init__(self, *, live_order_gateway: Any) -> None:
        self._live_order_gateway = live_order_gateway

    def create(self, *, trading_mode: str, safe_mode: bool, hard_stop: bool = False):
        if trading_mode == "live":
            return LiveExecutor(
                live_order_gateway=self._live_order_gateway,
                trading_mode=trading_mode,
                safe_mode=safe_mode,
                hard_stop=hard_stop,
            )

        return DemoExecutor(live_order_gateway=self._live_order_gateway)
