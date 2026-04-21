from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

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

    _SECTION_FRESHNESS_WINDOWS = {
        "trading": 300,
        "learning": 300,
        "recovery": 600,
        "promotion": 86400,
    }

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
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self._dashboard_summary_service = dashboard_summary_service
        self._promotion_dashboard_facade = promotion_dashboard_facade
        self._learning_service = learning_service
        self._execution_ledger = execution_ledger
        self._position_lifecycle_ledger = position_lifecycle_ledger
        self._position_store = position_store
        self._market_price_store = market_price_store
        self._timestamp_provider = timestamp_provider or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

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
        promotion_ready = self._promotion_dashboard_facade.is_ready_for_review()
        section_state_label = self._build_section_state_label(
            boot_state=boot_state,
            learning_enabled=learning_enabled,
            last_learning_event=last_learning_event,
            promotion_ready=promotion_ready,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
        )
        section_severity = self._build_section_severity(
            boot_state=boot_state,
            learning_enabled=learning_enabled,
            last_learning_event=last_learning_event,
            promotion_ready=promotion_ready,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
        )
        section_state_message = self._build_section_state_message(
            boot_state=boot_state,
            learning_enabled=learning_enabled,
            last_learning_event=last_learning_event,
            promotion_ready=promotion_ready,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
        )
        section_recommended_action = self._build_section_recommended_action(
            boot_state=boot_state,
            learning_enabled=learning_enabled,
            last_learning_event=last_learning_event,
            promotion_ready=promotion_ready,
            recent_stop_loss_reason=None if ledger_summary is None else ledger_summary.recent_stop_loss_reason,
        )
        section_metrics = self._build_section_metrics(
            boot_state=boot_state,
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
            last_promotion_reviewed_at=self._promotion_dashboard_facade.latest_reviewed_at(),
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            promotion_ready=promotion_ready,
        )
        section_updated_at = self._build_section_updated_at(
            last_fill_recorded_at=last_fill_recorded_at,
            last_signal_recorded_at=last_signal_recorded_at,
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            last_promotion_reviewed_at=self._promotion_dashboard_facade.latest_reviewed_at(),
        )
        current_time = self._timestamp_provider()
        section_stale = self._build_section_stale(
            section_updated_at=section_updated_at,
            current_time=current_time,
        )
        section_age_sec = self._build_section_age_sec(
            section_updated_at=section_updated_at,
            current_time=current_time,
        )
        section_freshness_state = self._build_section_freshness_state(
            section_updated_at=section_updated_at,
            section_stale=section_stale,
        )
        section_freshness_message = self._build_section_freshness_message(
            section_freshness_state=section_freshness_state,
        )
        section_freshness_label = self._build_section_freshness_label(
            section_freshness_state=section_freshness_state,
        )
        section_freshness_recommended_action = self._build_section_freshness_recommended_action(
            section_freshness_state=section_freshness_state,
        )
        section_freshness_severity = self._build_section_freshness_severity(
            section_freshness_state=section_freshness_state,
        )
        section_freshness_window_sec = self._build_section_freshness_window_sec()
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
            sections=self._build_sections(
                section_state_label=section_state_label,
                section_severity=section_severity,
                section_state_message=section_state_message,
                section_recommended_action=section_recommended_action,
                section_metrics=section_metrics,
                section_updated_at=section_updated_at,
                section_stale=section_stale,
                section_age_sec=section_age_sec,
                section_freshness_state=section_freshness_state,
                section_freshness_message=section_freshness_message,
                section_freshness_label=section_freshness_label,
                section_freshness_recommended_action=section_freshness_recommended_action,
                section_freshness_severity=section_freshness_severity,
                section_freshness_window_sec=section_freshness_window_sec,
            ),
            section_state_label=section_state_label,
            section_severity=section_severity,
            section_state_message=section_state_message,
            section_recommended_action=section_recommended_action,
            promotion_ready=promotion_ready,
        )
        if isinstance(summary, dict):
            return summary
        return self._dashboard_summary_service.to_payload(summary)

    @staticmethod
    def _build_section_state_label(
        *,
        boot_state: BootState,
        learning_enabled: bool,
        last_learning_event: str | None,
        promotion_ready: bool,
        recent_stop_loss_reason: str | None,
    ) -> dict[str, str]:
        if recent_stop_loss_reason is None:
            trading = "NORMAL"
        else:
            trading = "STOP_LOSS_TRIGGERED"

        if boot_state.hard_stop:
            recovery = "HARD_STOP"
        elif boot_state.safe_mode or boot_state.failure_stage is not None:
            recovery = "SAFE_MODE"
        else:
            recovery = "OK"

        if last_learning_event == "hard_stop_triggered":
            learning = "HARD_STOP_EVENT"
        elif learning_enabled:
            learning = "ACTIVE"
        else:
            learning = "DISABLED"

        promotion = "READY" if promotion_ready else "NOT_READY"
        return {
            "trading": trading,
            "learning": learning,
            "recovery": recovery,
            "promotion": promotion,
        }

    @staticmethod
    def _build_sections(
        *,
        section_state_label: dict[str, str],
        section_severity: dict[str, str],
        section_state_message: dict[str, str],
        section_recommended_action: dict[str, str],
        section_metrics: dict[str, dict[str, object]],
        section_updated_at: dict[str, str | None],
        section_stale: dict[str, bool],
        section_age_sec: dict[str, int | None],
        section_freshness_state: dict[str, str],
        section_freshness_message: dict[str, str],
        section_freshness_label: dict[str, str],
        section_freshness_recommended_action: dict[str, str],
        section_freshness_severity: dict[str, str],
        section_freshness_window_sec: dict[str, int],
    ) -> list[dict[str, object]]:
        ordered_section_keys = ("trading", "learning", "recovery", "promotion")
        ordered_section_names = {
            "trading": "Trading",
            "learning": "Learning",
            "recovery": "Recovery",
            "promotion": "Promotion",
        }
        return [
            {
                "key": key,
                "name": ordered_section_names[key],
                "state_label": section_state_label[key],
                "severity": section_severity[key],
                "state_message": section_state_message[key],
                "recommended_action": section_recommended_action[key],
                "updated_at": section_updated_at[key],
                "stale": section_stale[key],
                "age_sec": section_age_sec[key],
                "freshness_state": section_freshness_state[key],
                "freshness_message": section_freshness_message[key],
                "freshness_label": section_freshness_label[key],
                "freshness_recommended_action": section_freshness_recommended_action[key],
                "freshness_severity": section_freshness_severity[key],
                "freshness_window_sec": section_freshness_window_sec[key],
                "freshness_metric_items": DashboardSummaryFacade._build_section_freshness_metric_items(
                    updated_at=section_updated_at[key],
                    age_sec=section_age_sec[key],
                    freshness_window_sec=section_freshness_window_sec[key],
                ),
                "metrics": section_metrics[key],
                "metric_items": DashboardSummaryFacade._build_section_metric_items(
                    key=key,
                    metrics=section_metrics[key],
                ),
            }
            for key in ordered_section_keys
        ]

    @staticmethod
    def _build_section_metric_items(
        *,
        key: str,
        metrics: dict[str, object],
    ) -> list[dict[str, object]]:
        metric_labels = {
            "trading": [
                ("buy_count", "Buy Count"),
                ("sell_count", "Sell Count"),
                ("stop_loss_count", "Stop Loss Count"),
                ("realized_pnl", "Realized PnL"),
                ("unrealized_pnl", "Unrealized PnL"),
                ("recent_stop_loss_reason", "Recent Stop Loss Reason"),
            ],
            "learning": [
                ("last_learning_event", "Last Learning Event"),
                ("learning_signal_count", "Signal Count"),
                ("learning_fill_count", "Fill Count"),
                ("last_signal_recorded_at", "Last Signal At"),
                ("last_fill_recorded_at", "Last Fill At"),
            ],
            "recovery": [
                ("safe_mode", "Safe Mode"),
                ("hard_stop", "Hard Stop"),
                ("trading_ready", "Trading Ready"),
                ("failure_stage", "Failure Stage"),
                ("last_restart_detected_at", "Last Restart At"),
                ("last_recovery_completed_at", "Last Recovery At"),
            ],
            "promotion": [
                ("promotion_ready", "Promotion Ready"),
                ("last_promotion_reviewed_at", "Last Promotion Review At"),
            ],
        }
        metric_types = {
            "buy_count": "count",
            "sell_count": "count",
            "stop_loss_count": "count",
            "realized_pnl": "pnl",
            "unrealized_pnl": "pnl",
            "recent_stop_loss_reason": "text",
            "last_learning_event": "text",
            "learning_signal_count": "count",
            "learning_fill_count": "count",
            "last_signal_recorded_at": "timestamp",
            "last_fill_recorded_at": "timestamp",
            "safe_mode": "boolean",
            "hard_stop": "boolean",
            "trading_ready": "boolean",
            "failure_stage": "text",
            "last_restart_detected_at": "timestamp",
            "last_recovery_completed_at": "timestamp",
            "promotion_ready": "boolean",
            "last_promotion_reviewed_at": "timestamp",
        }
        metric_format_hints = {
            "buy_count": "integer",
            "sell_count": "integer",
            "stop_loss_count": "integer",
            "realized_pnl": "signed_currency",
            "unrealized_pnl": "signed_currency",
            "recent_stop_loss_reason": "plain_text",
            "last_learning_event": "plain_text",
            "learning_signal_count": "integer",
            "learning_fill_count": "integer",
            "last_signal_recorded_at": "datetime",
            "last_fill_recorded_at": "datetime",
            "safe_mode": "boolean_badge",
            "hard_stop": "boolean_badge",
            "trading_ready": "boolean_badge",
            "failure_stage": "plain_text",
            "last_restart_detected_at": "datetime",
            "last_recovery_completed_at": "datetime",
            "promotion_ready": "boolean_badge",
            "last_promotion_reviewed_at": "datetime",
        }
        return [
            {
                "key": metric_key,
                "label": label,
                "type": metric_types[metric_key],
                "format_hint": metric_format_hints[metric_key],
                "severity": DashboardSummaryFacade._resolve_metric_severity(
                    key=metric_key,
                    value=metrics[metric_key],
                ),
                "state_message": DashboardSummaryFacade._resolve_metric_state_message(
                    key=metric_key,
                    label=label,
                    value=metrics[metric_key],
                ),
                "value": metrics[metric_key],
            }
            for metric_key, label in metric_labels[key]
        ]

    @staticmethod
    def _resolve_metric_severity(
        *,
        key: str,
        value: object,
    ) -> str:
        if key == "stop_loss_count":
            return "critical" if isinstance(value, (int, float)) and value > 0 else "info"
        if key in {"realized_pnl", "unrealized_pnl"}:
            return "warning" if isinstance(value, (int, float)) and value < 0 else "info"
        if key == "recent_stop_loss_reason":
            return "critical" if value is not None else "info"
        if key == "safe_mode":
            return "warning" if value is True else "info"
        if key == "hard_stop":
            return "critical" if value is True else "info"
        if key in {"trading_ready", "promotion_ready"}:
            return "warning" if value is False else "info"
        if key == "failure_stage":
            return "warning" if value is not None else "info"
        return "info"

    @staticmethod
    def _resolve_metric_state_message(
        *,
        key: str,
        label: str,
        value: object,
    ) -> str:
        if key in {
            "buy_count",
            "sell_count",
            "stop_loss_count",
            "learning_signal_count",
            "learning_fill_count",
        }:
            return f"{label} {value}"
        if key in {"realized_pnl", "unrealized_pnl"}:
            if isinstance(value, (int, float)) and value < 0:
                return f"{label} 손실 {value}"
            if isinstance(value, (int, float)) and value > 0:
                return f"{label} 이익 {value}"
            return f"{label} {value}"
        if key == "safe_mode":
            return "Safe Mode 활성" if value is True else "Safe Mode 비활성"
        if key == "hard_stop":
            return "Hard Stop 활성" if value is True else "Hard Stop 비활성"
        if key == "trading_ready":
            return "Trading Ready 준비됨" if value is True else "Trading Ready 미준비"
        if key == "promotion_ready":
            return "Promotion Ready 준비됨" if value is True else "Promotion Ready 미준비"
        if value is None:
            return f"{label} 기록 없음"
        return f"{label} {value}"

    @staticmethod
    def _build_section_freshness_metric_items(
        *,
        updated_at: str | None,
        age_sec: int | None,
        freshness_window_sec: int,
    ) -> list[dict[str, object]]:
        return [
            {
                "key": "updated_at",
                "label": "Updated At",
                "type": "timestamp",
                "state_message": DashboardSummaryFacade._resolve_metric_state_message(
                    key="updated_at",
                    label="Updated At",
                    value=updated_at,
                ),
                "value": updated_at,
            },
            {
                "key": "age_sec",
                "label": "Age Seconds",
                "type": "duration_sec",
                "state_message": DashboardSummaryFacade._resolve_metric_state_message(
                    key="age_sec",
                    label="Age Seconds",
                    value=age_sec,
                ),
                "value": age_sec,
            },
            {
                "key": "freshness_window_sec",
                "label": "Freshness Window Seconds",
                "type": "window_sec",
                "state_message": DashboardSummaryFacade._resolve_metric_state_message(
                    key="freshness_window_sec",
                    label="Freshness Window Seconds",
                    value=freshness_window_sec,
                ),
                "value": freshness_window_sec,
            },
        ]

    @staticmethod
    def _build_section_updated_at(
        *,
        last_fill_recorded_at: str | None,
        last_signal_recorded_at: str | None,
        last_restart_detected_at: str | None,
        last_recovery_completed_at: str | None,
        last_promotion_reviewed_at: str | None,
    ) -> dict[str, str | None]:
        return {
            "trading": last_fill_recorded_at,
            "learning": last_fill_recorded_at or last_signal_recorded_at,
            "recovery": last_recovery_completed_at or last_restart_detected_at,
            "promotion": last_promotion_reviewed_at,
        }

    @staticmethod
    def _build_section_stale(
        *,
        section_updated_at: dict[str, str | None],
        current_time: str,
    ) -> dict[str, bool]:
        current_timestamp = DashboardSummaryFacade._parse_timestamp(current_time)
        return {
            key: DashboardSummaryFacade._is_stale(
                updated_at=updated_at,
                current_timestamp=current_timestamp,
                freshness_window_sec=DashboardSummaryFacade._SECTION_FRESHNESS_WINDOWS[key],
            )
            for key, updated_at in section_updated_at.items()
        }

    @classmethod
    def _build_section_freshness_window_sec(cls) -> dict[str, int]:
        return dict(cls._SECTION_FRESHNESS_WINDOWS)

    @staticmethod
    def _build_section_freshness_state(
        *,
        section_updated_at: dict[str, str | None],
        section_stale: dict[str, bool],
    ) -> dict[str, str]:
        return {
            key: DashboardSummaryFacade._resolve_freshness_state(
                updated_at=section_updated_at[key],
                stale=section_stale[key],
            )
            for key in section_updated_at
        }

    @staticmethod
    def _build_section_freshness_message(
        *,
        section_freshness_state: dict[str, str],
    ) -> dict[str, str]:
        messages = {
            "missing": "데이터 없음",
            "stale": "갱신 지연",
            "fresh": "최근 데이터",
        }
        return {
            key: messages[state]
            for key, state in section_freshness_state.items()
        }

    @staticmethod
    def _build_section_freshness_label(
        *,
        section_freshness_state: dict[str, str],
    ) -> dict[str, str]:
        labels = {
            "missing": "MISSING",
            "stale": "DELAYED",
            "fresh": "RECENT",
        }
        return {
            key: labels[state]
            for key, state in section_freshness_state.items()
        }

    @staticmethod
    def _build_section_freshness_recommended_action(
        *,
        section_freshness_state: dict[str, str],
    ) -> dict[str, str]:
        actions = {
            "missing": "데이터 소스와 수집 경로를 확인하세요.",
            "stale": "데이터 갱신 지연 원인을 점검하세요.",
            "fresh": "현재 갱신 상태를 유지하며 모니터링하세요.",
        }
        return {
            key: actions[state]
            for key, state in section_freshness_state.items()
        }

    @staticmethod
    def _build_section_freshness_severity(
        *,
        section_freshness_state: dict[str, str],
    ) -> dict[str, str]:
        severities = {
            "missing": "warning",
            "stale": "warning",
            "fresh": "info",
        }
        return {
            key: severities[state]
            for key, state in section_freshness_state.items()
        }

    @staticmethod
    def _build_section_age_sec(
        *,
        section_updated_at: dict[str, str | None],
        current_time: str,
    ) -> dict[str, int | None]:
        current_timestamp = DashboardSummaryFacade._parse_timestamp(current_time)
        return {
            key: DashboardSummaryFacade._calculate_age_sec(
                updated_at=updated_at,
                current_timestamp=current_timestamp,
            )
            for key, updated_at in section_updated_at.items()
        }

    @staticmethod
    def _is_stale(
        *,
        updated_at: str | None,
        current_timestamp: datetime | None,
        freshness_window_sec: int,
    ) -> bool:
        if updated_at is None or current_timestamp is None:
            return True
        updated_timestamp = DashboardSummaryFacade._parse_timestamp(updated_at)
        if updated_timestamp is None:
            return True
        age_seconds = (current_timestamp - updated_timestamp).total_seconds()
        return age_seconds > freshness_window_sec

    @staticmethod
    def _calculate_age_sec(
        *,
        updated_at: str | None,
        current_timestamp: datetime | None,
    ) -> int | None:
        if updated_at is None or current_timestamp is None:
            return None
        updated_timestamp = DashboardSummaryFacade._parse_timestamp(updated_at)
        if updated_timestamp is None:
            return None
        return max(0, int((current_timestamp - updated_timestamp).total_seconds()))

    @staticmethod
    def _resolve_freshness_state(
        *,
        updated_at: str | None,
        stale: bool,
    ) -> str:
        if updated_at is None:
            return "missing"
        return "stale" if stale else "fresh"

    @staticmethod
    def _parse_timestamp(timestamp: str) -> datetime | None:
        try:
            return datetime.fromisoformat(timestamp)
        except ValueError:
            return None

    @staticmethod
    def _build_section_metrics(
        *,
        boot_state: BootState,
        realized_pnl: float,
        unrealized_pnl: float,
        buy_count: int,
        sell_count: int,
        stop_loss_count: int,
        recent_stop_loss_reason: str | None,
        last_learning_event: str | None,
        learning_signal_count: int,
        learning_fill_count: int,
        last_signal_recorded_at: str | None,
        last_fill_recorded_at: str | None,
        last_promotion_reviewed_at: str | None,
        last_restart_detected_at: str | None,
        last_recovery_completed_at: str | None,
        promotion_ready: bool,
    ) -> dict[str, dict[str, object]]:
        return {
            "trading": {
                "buy_count": buy_count,
                "sell_count": sell_count,
                "stop_loss_count": stop_loss_count,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "recent_stop_loss_reason": recent_stop_loss_reason,
            },
            "learning": {
                "last_learning_event": last_learning_event,
                "learning_signal_count": learning_signal_count,
                "learning_fill_count": learning_fill_count,
                "last_signal_recorded_at": last_signal_recorded_at,
                "last_fill_recorded_at": last_fill_recorded_at,
            },
            "recovery": {
                "safe_mode": boot_state.safe_mode,
                "hard_stop": boot_state.hard_stop,
                "trading_ready": boot_state.trading_ready,
                "failure_stage": boot_state.failure_stage,
                "last_restart_detected_at": last_restart_detected_at,
                "last_recovery_completed_at": last_recovery_completed_at,
            },
            "promotion": {
                "promotion_ready": promotion_ready,
                "last_promotion_reviewed_at": last_promotion_reviewed_at,
            },
        }

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
