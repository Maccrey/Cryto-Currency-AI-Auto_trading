from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.execution.demo import FillResult
from app.services.risk.stop_loss import PositionSnapshot, StopLossInjector
from app.services.trading.execution import TradeExecutionResult, TradeExecutionService


@dataclass(frozen=True)
class PostFillResult:
    execution_result: TradeExecutionResult
    position: PositionSnapshot | None


class PostFillService:
    """Attach position risk metadata after a successful buy execution."""

    def __init__(self, *, stop_loss_injector: StopLossInjector) -> None:
        self._stop_loss_injector = stop_loss_injector

    def process(self, execution_result: TradeExecutionResult) -> PostFillResult:
        execution = execution_result.execution
        if (
            execution_result.status != "filled"
            or execution is None
            or not isinstance(execution, FillResult)
            or execution.side != "buy"
        ):
            return PostFillResult(
                execution_result=execution_result,
                position=None,
            )

        position = self._stop_loss_injector.inject(
            market=execution.market,
            signal_level=execution_result.decision.signal.level,
            entry_price=execution.filled_price,
            quantity=execution.filled_quantity,
        )
        return PostFillResult(
            execution_result=execution_result,
            position=position,
        )

    @staticmethod
    def to_payload(result: PostFillResult) -> dict[str, object]:
        payload = {
            "execution": TradeExecutionService.to_payload(result.execution_result),
            "position": None,
        }
        if result.position is not None:
            payload["position"] = asdict(result.position)
        return payload
