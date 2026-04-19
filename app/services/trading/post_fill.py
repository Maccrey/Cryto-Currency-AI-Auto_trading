from __future__ import annotations

from dataclasses import asdict, dataclass

from app.integrations.telegram.notifier import TelegramNotifier
from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.risk.stop_loss import PositionSnapshot, StopLossInjector
from app.services.trading.execution import TradeExecutionResult, TradeExecutionService


@dataclass(frozen=True)
class PostFillResult:
    execution_result: TradeExecutionResult
    position: PositionSnapshot | None


class PostFillService:
    """Attach position risk metadata after a successful buy execution."""

    def __init__(
        self,
        *,
        stop_loss_injector: StopLossInjector,
        position_store: CurrentPositionStore | None = None,
        telegram_notifier: TelegramNotifier | None = None,
        execution_ledger: ExecutionLedger | None = None,
        position_lifecycle_ledger: PositionLifecycleLedger | None = None,
    ) -> None:
        self._stop_loss_injector = stop_loss_injector
        self._position_store = position_store
        self._telegram_notifier = telegram_notifier
        self._execution_ledger = execution_ledger
        self._position_lifecycle_ledger = position_lifecycle_ledger

    def process(self, execution_result: TradeExecutionResult) -> PostFillResult:
        execution = execution_result.execution
        if (
            execution_result.status != "filled"
            or execution is None
            or not isinstance(execution, FillResult)
        ):
            return PostFillResult(
                execution_result=execution_result,
                position=None,
            )
        if execution.side != "buy":
            if self._position_store is not None:
                self._position_store.clear()
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
        if self._position_store is not None:
            self._position_store.save(position)
        if self._position_lifecycle_ledger is not None:
            self._position_lifecycle_ledger.record(
                event_type="opened",
                position=position,
            )
        if self._execution_ledger is not None:
            self._execution_ledger.record_fill(execution)
        if self._telegram_notifier is not None:
            self._telegram_notifier.notify_fill(execution)
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
