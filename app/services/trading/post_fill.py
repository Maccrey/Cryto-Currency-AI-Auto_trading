from __future__ import annotations

from dataclasses import asdict, dataclass

from app.integrations.telegram.notifier import TelegramNotifier
from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningEvent, LearningService
from app.services.portfolio.sync import PortfolioState
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
        initial_portfolio_state: PortfolioState | None = None,
        position_lifecycle_ledger: PositionLifecycleLedger | None = None,
        learning_service: LearningService | None = None,
    ) -> None:
        self._stop_loss_injector = stop_loss_injector
        self._position_store = position_store
        self._telegram_notifier = telegram_notifier
        self._execution_ledger = execution_ledger
        self._initial_portfolio_state = initial_portfolio_state
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._learning_service = learning_service

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
        existing_position = None if self._position_store is None else self._position_store.get()
        event_type = "opened"
        if existing_position is not None and existing_position.market == position.market:
            position = self._merge_position(
                existing_position=existing_position,
                added_position=position,
                added_fee=execution.fee,
            )
            event_type = "increased"
        if self._position_store is not None:
            self._position_store.save(position)
        if self._position_lifecycle_ledger is not None:
            self._position_lifecycle_ledger.record(
                event_type=event_type,
                position=position,
            )
        regime_payload = self._regime_payload(getattr(execution_result.decision, "regime", None))
        if self._learning_service is not None:
            self._learning_service.record(
                LearningEvent(
                    event_name="position_opened",
                    market=position.market,
                    mode=execution.mode,
                    payload={
                        "signal_level": position.signal_level,
                        "entry_price": position.entry_price,
                        "quantity": position.quantity,
                        "stop_loss_price": position.stop_loss_price,
                        "event_type": event_type,
                        "validation_window_sec": position.validation_window_sec,
                        "min_expected_return_pct": position.min_expected_return_pct,
                        **regime_payload,
                    },
                ),
            )
        if self._execution_ledger is not None:
            self._execution_ledger.record_fill(
                execution,
                signal_level=execution_result.decision.signal.level,
                signal_score=execution_result.decision.signal.score,
                market_state=regime_payload.get("market_state"),
                market_state_label=regime_payload.get("market_state_label"),
                box_range_low=regime_payload.get("box_range_low"),
                box_range_high=regime_payload.get("box_range_high"),
            )
        if self._telegram_notifier is not None:
            total_asset_value = self._total_asset_value_after_fill(
                current_price=execution.filled_price,
            )
            self._telegram_notifier.notify_fill(
                execution,
                total_asset_value=total_asset_value,
            )
        return PostFillResult(
            execution_result=execution_result,
            position=position,
        )

    @staticmethod
    def _regime_payload(regime) -> dict[str, object]:
        if regime is None:
            return {}
        return {
            "market_state": getattr(regime, "market_state", None),
            "market_state_label": getattr(regime, "market_state_label", None),
            "box_range_low": getattr(regime, "box_range_low", None),
            "box_range_high": getattr(regime, "box_range_high", None),
            "regime_label": getattr(regime, "label", None),
            "regime_score": getattr(regime, "score", None),
        }

    def _total_asset_value_after_fill(self, *, current_price: float) -> float | None:
        if self._execution_ledger is None or self._initial_portfolio_state is None:
            return None
        portfolio = self._execution_ledger.portfolio_state(
            initial_cash=self._initial_portfolio_state.cash_balance,
            asset_currency=self._initial_portfolio_state.asset_currency,
        )
        return round(portfolio.cash_balance + (portfolio.asset_balance * current_price), 2)

    @staticmethod
    def _merge_position(
        *,
        existing_position: PositionSnapshot,
        added_position: PositionSnapshot,
        added_fee: float,
    ) -> PositionSnapshot:
        total_quantity = round(existing_position.quantity + added_position.quantity, 8)
        if total_quantity <= 0:
            return added_position
        total_cost = (
            existing_position.entry_price * existing_position.quantity
            + added_position.entry_price * added_position.quantity
            + added_fee
        )
        entry_price = round(total_cost / total_quantity, 8)
        stop_loss_pct = max(existing_position.stop_loss_pct, added_position.stop_loss_pct)
        return PositionSnapshot(
            market=existing_position.market,
            signal_level=added_position.signal_level,
            entry_price=entry_price,
            quantity=total_quantity,
            stop_loss_price=round(entry_price * (1 - stop_loss_pct), 2),
            stop_loss_pct=stop_loss_pct,
            validation_window_sec=added_position.validation_window_sec,
            min_expected_return_pct=added_position.min_expected_return_pct,
            stop_loss_reason=None,
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
