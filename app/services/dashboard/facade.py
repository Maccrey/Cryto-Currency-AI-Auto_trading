from __future__ import annotations

from app.services.execution.ledger import ExecutionLedger
from app.services.dashboard.summary import DashboardSummaryService
from app.services.learning.service import LearningService
from app.services.market.store import MarketPriceStore
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.recovery.orchestrator import BootState


class DashboardSummaryFacade:
    """Compose dashboard summary payloads from runtime and promotion state."""

    def __init__(
        self,
        *,
        dashboard_summary_service: DashboardSummaryService,
        promotion_dashboard_facade: PromotionDashboardFacade,
        learning_service: LearningService | None = None,
        execution_ledger: ExecutionLedger | None = None,
        position_lifecycle_ledger: PositionLifecycleLedger | None = None,
        position_store: CurrentPositionStore | None = None,
        market_price_store: MarketPriceStore | None = None,
    ) -> None:
        self._dashboard_summary_service = dashboard_summary_service
        self._promotion_dashboard_facade = promotion_dashboard_facade
        self._learning_service = learning_service
        self._execution_ledger = execution_ledger
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._position_store = position_store
        self._market_price_store = market_price_store

    def build_response(
        self,
        *,
        boot_state: BootState,
        trading_mode: str,
        learning_enabled: bool,
    ) -> dict[str, object]:
        ledger_summary = None if self._execution_ledger is None else self._execution_ledger.summarize()
        recent_learning_events = [] if self._learning_service is None else self._learning_service.recent_events()
        last_learning_event = None if not recent_learning_events else recent_learning_events[-1].event_name
        learning_signal_count = sum(
            1 for event in recent_learning_events if event.event_name.startswith("signal_")
        )
        learning_fill_count = sum(
            1 for event in recent_learning_events if event.event_name.startswith("fill_")
        )
        last_signal_recorded_at = next(
            (
                event.recorded_at
                for event in reversed(recent_learning_events)
                if event.event_name.startswith("signal_")
            ),
            None,
        )
        last_fill_recorded_at = next(
            (
                event.recorded_at
                for event in reversed(recent_learning_events)
                if event.event_name.startswith("fill_")
            ),
            None,
        )
        last_restart_detected_at = next(
            (
                event.recorded_at
                for event in reversed(recent_learning_events)
                if event.event_name == "restart_detected"
            ),
            None,
        )
        last_recovery_completed_at = next(
            (
                event.recorded_at
                for event in reversed(recent_learning_events)
                if event.event_name == "recovery_completed"
            ),
            None,
        )
        position_records = (
            [] if self._position_lifecycle_ledger is None else self._position_lifecycle_ledger.list_records(limit=1)
        )
        last_position_event = None if not position_records else position_records[-1].event_type
        unrealized_pnl = 0.0
        if self._position_store is not None and self._market_price_store is not None:
            position = self._position_store.get()
            if position is not None:
                latest_price = self._market_price_store.get_price(position.market)
                if latest_price is not None:
                    unrealized_pnl = round(
                        (latest_price - position.entry_price) * position.quantity,
                        2,
                    )
        summary = self._dashboard_summary_service.build(
            boot_state=boot_state,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
            realized_pnl=0.0 if ledger_summary is None else ledger_summary.realized_pnl,
            unrealized_pnl=unrealized_pnl,
            buy_count=0 if ledger_summary is None else ledger_summary.buy_count,
            sell_count=0 if ledger_summary is None else ledger_summary.sell_count,
            stop_loss_count=0 if ledger_summary is None else ledger_summary.stop_loss_count,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
            last_learning_event=last_learning_event,
            learning_signal_count=learning_signal_count,
            learning_fill_count=learning_fill_count,
            last_signal_recorded_at=last_signal_recorded_at,
            last_fill_recorded_at=last_fill_recorded_at,
            last_position_event=last_position_event,
            last_promotion_reviewed_at=self._promotion_dashboard_facade.latest_reviewed_at(),
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            section_severity=self._build_section_severity(
                boot_state=boot_state,
                learning_enabled=learning_enabled,
                last_learning_event=last_learning_event,
                promotion_ready=self._promotion_dashboard_facade.is_ready_for_review(),
                recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
            ),
            promotion_ready=self._promotion_dashboard_facade.is_ready_for_review(),
        )
        if isinstance(summary, dict):
            return summary
        return self._dashboard_summary_service.to_payload(summary)

    @staticmethod
    def _build_section_severity(
        *,
        boot_state: BootState,
        learning_enabled: bool,
        last_learning_event: str | None,
        promotion_ready: bool,
        recent_stop_loss_reason: str | None,
    ) -> dict[str, str]:
        trading = "critical" if recent_stop_loss_reason else "info"
        if boot_state.hard_stop:
            recovery = "critical"
        elif boot_state.safe_mode or boot_state.failure_stage is not None:
            recovery = "warning"
        else:
            recovery = "info"
        if last_learning_event == "hard_stop_triggered":
            learning = "critical"
        elif learning_enabled:
            learning = "info"
        else:
            learning = "warning"
        promotion = "info" if promotion_ready else "warning"
        return {
            "trading": trading,
            "learning": learning,
            "recovery": recovery,
            "promotion": promotion,
        }
