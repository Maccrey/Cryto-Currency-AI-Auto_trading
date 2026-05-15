from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.execution.demo import FillResult, OrderIntent
from app.services.execution.live import LiveExecutionResult
from app.services.execution.rules import UpbitOrderRules
from app.services.trading.decision import TradeDecisionResult


@dataclass(frozen=True)
class TradeExecutionResult:
    decision: TradeDecisionResult
    execution: FillResult | LiveExecutionResult | None
    status: str
    blocked_reason: str | None


class TradeExecutionService:
    """Convert sizing-approved decisions into executable order intents."""

    def __init__(
        self,
        *,
        executor: Any,
        market: str,
        order_rules: UpbitOrderRules | None = None,
    ) -> None:
        self._executor = executor
        self._market = market
        self._order_rules = order_rules or UpbitOrderRules()

    def execute(self, decision: TradeDecisionResult) -> TradeExecutionResult:
        if not decision.sizing.allowed:
            return TradeExecutionResult(
                decision=decision,
                execution=None,
                status="blocked",
                blocked_reason=decision.sizing.blocked_reason,
            )

        execution_price = 0.0
        if decision.sizing.buy_quantity > 0:
            execution_price = round(
                decision.sizing.buy_amount / decision.sizing.buy_quantity,
                8,
            )
        if not self._order_rules.is_allowed(
            market=self._market,
            price=execution_price,
            quantity=decision.sizing.buy_quantity,
        ):
            return TradeExecutionResult(
                decision=decision,
                execution=None,
                status="blocked",
                blocked_reason="MIN_ORDER_AMOUNT",
            )
        intent = OrderIntent(
            market=self._market,
            side=decision.sizing.order_side,
            price=execution_price,
            quantity=decision.sizing.buy_quantity,
            order_type="market",
            is_stop_loss=False,
        )

        execution = self._executor.execute(intent)
        blocked_reason = getattr(execution, "blocked_reason", None)
        status = getattr(execution, "status", "unknown")
        return TradeExecutionResult(
            decision=decision,
            execution=execution,
            status=status,
            blocked_reason=blocked_reason,
        )

    def order_status(self, order_id: str) -> dict[str, object]:
        order_status = getattr(self._executor, "order_status", None)
        if order_status is None:
            return {
                "order_id": order_id,
                "state": "unknown",
                "blocked_reason": "ORDER_STATUS_UNAVAILABLE",
            }
        return order_status(order_id)

    @staticmethod
    def to_payload(result: TradeExecutionResult) -> dict[str, object]:
        execution_payload = None
        if result.execution is not None:
            execution_payload = asdict(result.execution)
        return {
            "status": result.status,
            "blocked_reason": result.blocked_reason,
            "execution": execution_payload,
        }
