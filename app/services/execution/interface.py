from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.services.execution.demo import OrderIntent


@runtime_checkable
class ExecutionExecutor(Protocol):
    """Common execution interface shared by demo and live executors."""

    def execute(self, intent: OrderIntent) -> Any:
        """Execute an order intent and return the mode-specific result."""
