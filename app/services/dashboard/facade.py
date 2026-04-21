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
            section_state_message=self._build_section_state_message(
                boot_state=boot_state,
                learning_enabled=learning_enabled,
                last_learning_event=last_learning_event,
                promotion_ready=self._promotion_dashboard_facade.is_ready_for_review(),
                recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
            ),
            section_recommended_action=self._build_section_recommended_action(
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

    @staticmethod
    def _build_section_state_message(
        *,
        boot_state: BootState,
        learning_enabled: bool,
        last_learning_event: str | None,
        promotion_ready: bool,
        recent_stop_loss_reason: str | None,
    ) -> dict[str, str]:
        if recent_stop_loss_reason is None:
            trading = "최근 체결 기준 거래 리스크 이상이 없습니다."
        else:
            trading = f"최근 손절 사유: {recent_stop_loss_reason}"

        if boot_state.hard_stop:
            recovery = "하드스톱이 활성화되어 수동 개입이 필요합니다."
        elif boot_state.safe_mode or boot_state.failure_stage is not None:
            recovery = "복구 경로에서 안전 모드가 유지되고 있습니다."
        else:
            recovery = "복구 상태가 정상입니다."

        if last_learning_event == "hard_stop_triggered":
            learning = "최근 학습 이벤트에 하드스톱 트리거가 기록되었습니다."
        elif learning_enabled:
            learning = "학습 이벤트 기록이 활성화되어 있습니다."
        else:
            learning = "학습 이벤트 기록이 비활성화되어 있습니다."

        if promotion_ready:
            promotion = "실거래 승격 검토 준비가 완료되었습니다."
        else:
            promotion = "실거래 승격 검토 준비가 아직 완료되지 않았습니다."

        return {
            "trading": trading,
            "learning": learning,
            "recovery": recovery,
            "promotion": promotion,
        }

    @staticmethod
    def _build_section_recommended_action(
        *,
        boot_state: BootState,
        learning_enabled: bool,
        last_learning_event: str | None,
        promotion_ready: bool,
        recent_stop_loss_reason: str | None,
    ) -> dict[str, str]:
        if recent_stop_loss_reason is None:
            trading = "현재 거래 섹션은 모니터링만 유지하세요."
        else:
            trading = "최근 손절 발생 원인과 청산 흐름을 점검하세요."

        if boot_state.hard_stop:
            recovery = "하드스톱 해제 전까지 수동 점검과 원인 분석을 진행하세요."
        elif boot_state.safe_mode or boot_state.failure_stage is not None:
            recovery = "복구 실패 지점을 확인하고 안전 모드 해제 조건을 점검하세요."
        else:
            recovery = "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요."

        if last_learning_event == "hard_stop_triggered":
            learning = "하드스톱 관련 학습 이벤트 적재 상태를 우선 확인하세요."
        elif learning_enabled:
            learning = "학습 로그 적재가 유지되는지만 주기적으로 확인하세요."
        else:
            learning = "학습 기능 활성화 여부와 설정값을 다시 확인하세요."

        if promotion_ready:
            promotion = "승격 검토 또는 수동 승인 절차를 진행하세요."
        else:
            promotion = "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요."

        return {
            "trading": trading,
            "learning": learning,
            "recovery": recovery,
            "promotion": promotion,
        }
