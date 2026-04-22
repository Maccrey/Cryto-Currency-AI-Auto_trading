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
                **(
                    section_action_state := DashboardSummaryFacade._build_section_action_state(
                        key=key,
                        state_label=section_state_label[key],
                    )
                ),
                **{
                    "key": key,
                    "name": ordered_section_names[key],
                    "state_label": section_state_label[key],
                    "severity": section_severity[key],
                    "state_message": section_state_message[key],
                    "recommended_action": section_recommended_action[key],
                    "state_object": DashboardSummaryFacade._build_section_state_object(
                        state_label=section_state_label[key],
                        severity=section_severity[key],
                        state_message=section_state_message[key],
                        recommended_action=section_recommended_action[key],
                    ),
                    "recommended_action_label": section_action_state["recommended_action_label"],
                    "action_group": section_action_state["action_group"],
                    "action_priority": section_action_state["action_priority"],
                    "actionable": section_action_state["actionable"],
                },
                **DashboardSummaryFacade._build_section_route_fields(key=key),
                "updated_at": section_updated_at[key],
                "stale": section_stale[key],
                "age_sec": section_age_sec[key],
                "freshness_state": section_freshness_state[key],
                "freshness_message": section_freshness_message[key],
                "freshness_label": section_freshness_label[key],
                "freshness_recommended_action": section_freshness_recommended_action[key],
                "freshness_severity": section_freshness_severity[key],
                "freshness_window_sec": section_freshness_window_sec[key],
                "freshness_state_object": DashboardSummaryFacade._build_section_freshness_snapshot(
                    updated_at=section_updated_at[key],
                    stale=section_stale[key],
                    age_sec=section_age_sec[key],
                    freshness_state=section_freshness_state[key],
                    freshness_message=section_freshness_message[key],
                    freshness_label=section_freshness_label[key],
                    freshness_recommended_action=section_freshness_recommended_action[key],
                    freshness_severity=section_freshness_severity[key],
                    freshness_window_sec=section_freshness_window_sec[key],
                ),
                "freshness_metric_items": DashboardSummaryFacade._build_section_freshness_metric_items(
                    section_key=key,
                    updated_at=section_updated_at[key],
                    age_sec=section_age_sec[key],
                    freshness_window_sec=section_freshness_window_sec[key],
                ),
                "metrics": section_metrics[key],
                "metric_items": DashboardSummaryFacade._build_section_metric_items(
                    key=key,
                    metrics=section_metrics[key],
                ),
                "section_objects": {
                    "state": DashboardSummaryFacade._build_section_state_object(
                        state_label=section_state_label[key],
                        severity=section_severity[key],
                        state_message=section_state_message[key],
                        recommended_action=section_recommended_action[key],
                    ),
                    "action": section_action_state["action_state"],
                    "freshness": DashboardSummaryFacade._build_section_freshness_snapshot(
                        updated_at=section_updated_at[key],
                        stale=section_stale[key],
                        age_sec=section_age_sec[key],
                        freshness_state=section_freshness_state[key],
                        freshness_message=section_freshness_message[key],
                        freshness_label=section_freshness_label[key],
                        freshness_recommended_action=section_freshness_recommended_action[key],
                        freshness_severity=section_freshness_severity[key],
                        freshness_window_sec=section_freshness_window_sec[key],
                    ),
                    "route": DashboardSummaryFacade._build_section_action_route(key=key),
                },
                "card_object": DashboardSummaryFacade._build_section_card_object(
                    key=key,
                    state_label=section_state_label[key],
                    severity=section_severity[key],
                    state_message=section_state_message[key],
                    recommended_action=section_recommended_action[key],
                    action_state=section_action_state["action_state"],
                    updated_at=section_updated_at[key],
                    stale=section_stale[key],
                    age_sec=section_age_sec[key],
                    freshness_state=section_freshness_state[key],
                    freshness_message=section_freshness_message[key],
                    freshness_label=section_freshness_label[key],
                    freshness_recommended_action=section_freshness_recommended_action[key],
                    freshness_severity=section_freshness_severity[key],
                    freshness_window_sec=section_freshness_window_sec[key],
                    metrics=section_metrics[key],
                ),
            }
            for key in ordered_section_keys
        ]

    @staticmethod
    def _build_section_route_fields(
        *,
        key: str,
    ) -> dict[str, object]:
        action_route = DashboardSummaryFacade._build_section_action_route(key=key)
        return {
            "action_url_key": action_route["url_key"],
            "action_tab_key": action_route["tab_key"],
            "action_target": action_route["target"],
            "action_params": action_route["params"],
            "action_route": action_route,
        }

    @staticmethod
    def _build_section_action_state(
        *,
        key: str,
        state_label: str,
    ) -> dict[str, object]:
        recommended_action_label = DashboardSummaryFacade._resolve_section_recommended_action_label(
            key=key,
            state_label=state_label,
        )
        action_group = DashboardSummaryFacade._resolve_metric_action_group(
            recommended_action_label,
        )
        return {
            "recommended_action_label": recommended_action_label,
            "action_group": action_group,
            "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                action_group,
            ),
            "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                action_group,
            ),
            "action_state": {
                "recommended_action_label": recommended_action_label,
                "action_group": action_group,
                "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                    action_group,
                ),
                "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                    action_group,
                ),
            },
        }

    @staticmethod
    def _build_section_state_object(
        *,
        state_label: str,
        severity: str,
        state_message: str,
        recommended_action: str,
    ) -> dict[str, str]:
        return {
            "state_label": state_label,
            "severity": severity,
            "state_message": state_message,
            "recommended_action": recommended_action,
        }

    @staticmethod
    def _build_section_freshness_snapshot(
        *,
        updated_at: str | None,
        stale: bool,
        age_sec: int | None,
        freshness_state: str,
        freshness_message: str,
        freshness_label: str,
        freshness_recommended_action: str,
        freshness_severity: str,
        freshness_window_sec: int,
    ) -> dict[str, object]:
        return {
            "updated_at": updated_at,
            "stale": stale,
            "age_sec": age_sec,
            "freshness_state": freshness_state,
            "freshness_message": freshness_message,
            "freshness_label": freshness_label,
            "freshness_recommended_action": freshness_recommended_action,
            "freshness_severity": freshness_severity,
            "freshness_window_sec": freshness_window_sec,
        }

    @staticmethod
    def _build_section_card_object(
        *,
        key: str,
        state_label: str,
        severity: str,
        state_message: str,
        recommended_action: str,
        action_state: dict[str, object],
        updated_at: str | None,
        stale: bool,
        age_sec: int | None,
        freshness_state: str,
        freshness_message: str,
        freshness_label: str,
        freshness_recommended_action: str,
        freshness_severity: str,
        freshness_window_sec: int,
        metrics: dict[str, object],
    ) -> dict[str, object]:
        return {
            "state": DashboardSummaryFacade._build_section_state_object(
                state_label=state_label,
                severity=severity,
                state_message=state_message,
                recommended_action=recommended_action,
            ),
            "action": action_state,
            "freshness": DashboardSummaryFacade._build_section_freshness_snapshot(
                updated_at=updated_at,
                stale=stale,
                age_sec=age_sec,
                freshness_state=freshness_state,
                freshness_message=freshness_message,
                freshness_label=freshness_label,
                freshness_recommended_action=freshness_recommended_action,
                freshness_severity=freshness_severity,
                freshness_window_sec=freshness_window_sec,
            ),
            "route": DashboardSummaryFacade._build_section_action_route(key=key),
            "metrics": metrics,
            "metric_items": DashboardSummaryFacade._build_section_metric_items(
                key=key,
                metrics=metrics,
            ),
            "freshness_metric_items": DashboardSummaryFacade._build_section_freshness_metric_items(
                section_key=key,
                updated_at=updated_at,
                age_sec=age_sec,
                freshness_window_sec=freshness_window_sec,
            ),
        }

    @staticmethod
    def _resolve_section_recommended_action_label(
        *,
        key: str,
        state_label: str,
    ) -> str:
        if key == "trading":
            return "REVIEW_TRADING_SECTION" if state_label == "STOP_LOSS_TRIGGERED" else "MONITOR_TRADING_SECTION"
        if key == "learning":
            return "MONITOR_LEARNING_SECTION" if state_label == "ACTIVE" else "CHECK_LEARNING_SECTION"
        if key == "recovery":
            return "CHECK_RECOVERY_SECTION" if state_label in {"SAFE_MODE", "HARD_STOP", "DEGRADED"} else "MONITOR_RECOVERY_SECTION"
        if key == "promotion":
            return "PROCEED_PROMOTION_SECTION" if state_label == "READY" else "IMPROVE_PROMOTION_SECTION"
        return "MONITOR_SECTION"

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
                "recommended_action": DashboardSummaryFacade._resolve_metric_recommended_action(
                    key=metric_key,
                    value=metrics[metric_key],
                ),
                "recommended_action_label": DashboardSummaryFacade._resolve_metric_recommended_action_label(
                    key=metric_key,
                    value=metrics[metric_key],
                ),
                "action_group": DashboardSummaryFacade._resolve_metric_action_group(
                    DashboardSummaryFacade._resolve_metric_recommended_action_label(
                        key=metric_key,
                        value=metrics[metric_key],
                    )
                ),
                "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key=metric_key,
                            value=metrics[metric_key],
                        )
                    )
                ),
                "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key=metric_key,
                            value=metrics[metric_key],
                        )
                    )
                ),
                "action_url_key": DashboardSummaryFacade._resolve_metric_action_url_key(
                    section_key=key,
                    metric_key=metric_key,
                ),
                "action_tab_key": DashboardSummaryFacade._resolve_metric_action_tab_key(
                    section_key=key,
                    metric_key=metric_key,
                ),
                "action_target": DashboardSummaryFacade._resolve_metric_action_target(
                    section_key=key,
                    metric_key=metric_key,
                ),
                "action_params": DashboardSummaryFacade._resolve_metric_action_params(
                    section_key=key,
                    metric_key=metric_key,
                ),
                "action_route": DashboardSummaryFacade._build_metric_action_route(
                    section_key=key,
                    metric_key=metric_key,
                ),
                "value": metrics[metric_key],
            }
            for metric_key, label in metric_labels[key]
        ]

    @staticmethod
    def _build_section_action_route(
        *,
        key: str,
    ) -> dict[str, object]:
        route_map = {
            "trading": {
                "url_key": "dashboard.executions",
                "tab_key": "timeline",
                "target": "execution_timeline",
                "params": {"section": "trading"},
            },
            "learning": {
                "url_key": "dashboard.learning",
                "tab_key": "recent-events",
                "target": "learning_recent_events",
                "params": {"section": "learning"},
            },
            "recovery": {
                "url_key": "dashboard.recovery",
                "tab_key": "status",
                "target": "recovery_status",
                "params": {"section": "recovery"},
            },
            "promotion": {
                "url_key": "dashboard.promotion",
                "tab_key": "status",
                "target": "promotion_status",
                "params": {"section": "promotion"},
            },
        }
        return route_map[key]

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
    def _resolve_metric_recommended_action(
        *,
        key: str,
        value: object,
    ) -> str:
        if key == "stop_loss_count":
            return (
                "최근 손절 흐름과 청산 원인을 점검하세요."
                if isinstance(value, (int, float)) and value > 0
                else "손절 카운트를 계속 모니터링하세요."
            )
        if key in {"realized_pnl", "unrealized_pnl"}:
            if isinstance(value, (int, float)) and value < 0:
                return "손익 악화 원인과 리스크 설정을 점검하세요."
            return "손익 흐름을 유지하며 모니터링하세요."
        if key == "recent_stop_loss_reason":
            return "최근 손절 사유를 검토하고 재진입 조건을 점검하세요." if value is not None else "손절 사유 발생 여부만 모니터링하세요."
        if key == "safe_mode":
            return "SAFE_MODE 해제 전까지 원인 분석을 진행하세요." if value is True else "현재 복구 상태를 유지하며 모니터링하세요."
        if key == "hard_stop":
            return "하드스톱 해제 전까지 수동 점검과 원인 분석을 진행하세요." if value is True else "하드스톱 조건 발생 여부를 계속 모니터링하세요."
        if key == "trading_ready":
            return "거래 준비 상태를 유지하세요." if value is True else "거래 준비 실패 원인을 점검하세요."
        if key == "promotion_ready":
            return "승격 검토 또는 승인 절차를 진행하세요." if value is True else "승격 기준 미달 항목을 보완하세요."
        if key == "failure_stage":
            return "실패 단계 원인을 확인하고 복구 절차를 점검하세요." if value is not None else "현재 실패 단계 없이 정상 상태를 유지하세요."
        if key in {"updated_at", "age_sec"}:
            return "최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요." if value is not None else "데이터 갱신 경로를 확인하세요."
        if key == "freshness_window_sec":
            return "freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요."
        if key in {
            "buy_count",
            "sell_count",
            "learning_signal_count",
            "learning_fill_count",
            "last_learning_event",
            "last_signal_recorded_at",
            "last_fill_recorded_at",
            "last_restart_detected_at",
            "last_recovery_completed_at",
            "last_promotion_reviewed_at",
        }:
            return "현재 기록 흐름을 유지하며 모니터링하세요." if value is not None else "해당 기록 경로를 확인하세요."
        return "현재 메트릭 상태를 유지하며 모니터링하세요."

    @staticmethod
    def _resolve_metric_recommended_action_label(
        *,
        key: str,
        value: object,
    ) -> str:
        if key == "stop_loss_count":
            return (
                "REVIEW_STOP_LOSS"
                if isinstance(value, (int, float)) and value > 0
                else "MONITOR_STOP_LOSS"
            )
        if key in {"realized_pnl", "unrealized_pnl"}:
            return "REVIEW_PNL" if isinstance(value, (int, float)) and value < 0 else "MONITOR_PNL"
        if key == "recent_stop_loss_reason":
            return "REVIEW_STOP_LOSS_REASON" if value is not None else "MONITOR_STOP_LOSS_REASON"
        if key == "safe_mode":
            return "CHECK_SAFE_MODE" if value is True else "MONITOR_RECOVERY"
        if key == "hard_stop":
            return "CHECK_HARD_STOP" if value is True else "MONITOR_HARD_STOP"
        if key == "trading_ready":
            return "MAINTAIN_TRADING_READY" if value is True else "CHECK_TRADING_READY"
        if key == "promotion_ready":
            return "PROCEED_PROMOTION" if value is True else "IMPROVE_PROMOTION"
        if key == "failure_stage":
            return "CHECK_FAILURE_STAGE" if value is not None else "MAINTAIN_NORMAL_STATE"
        if key in {"updated_at", "age_sec"}:
            return "MONITOR_FRESHNESS" if value is not None else "CHECK_DATA_SOURCE"
        if key == "freshness_window_sec":
            return "REFERENCE_FRESHNESS_WINDOW"
        if key in {
            "buy_count",
            "sell_count",
            "learning_signal_count",
            "learning_fill_count",
            "last_learning_event",
            "last_signal_recorded_at",
            "last_fill_recorded_at",
            "last_restart_detected_at",
            "last_recovery_completed_at",
            "last_promotion_reviewed_at",
        }:
            return "MONITOR_ACTIVITY" if value is not None else "CHECK_ACTIVITY_SOURCE"
        return "MONITOR_METRIC"

    @staticmethod
    def _resolve_metric_action_group(label: str) -> str:
        if label.startswith("PROCEED_"):
            return "proceed"
        if label.startswith("CHECK_"):
            return "check"
        if label.startswith("REVIEW_") or label.startswith("IMPROVE_"):
            return "review"
        if label.startswith("REFERENCE_"):
            return "reference"
        if label.startswith("MONITOR_") or label.startswith("MAINTAIN_"):
            return "monitor"
        return "monitor"

    @staticmethod
    def _resolve_metric_action_priority(action_group: str) -> str:
        if action_group in {"proceed", "review", "check"}:
            return "high"
        if action_group == "reference":
            return "medium"
        return "low"

    @staticmethod
    def _resolve_metric_actionable(action_group: str) -> bool:
        return action_group in {"proceed", "review", "check"}

    @staticmethod
    def _resolve_metric_action_url_key(
        *,
        section_key: str,
        metric_key: str,
    ) -> str:
        metric_url_keys = {
            "buy_count": "dashboard.executions",
            "sell_count": "dashboard.executions",
            "stop_loss_count": "dashboard.positions.history",
            "realized_pnl": "dashboard.executions",
            "unrealized_pnl": "dashboard.positions.current",
            "recent_stop_loss_reason": "dashboard.positions.history",
            "last_learning_event": "dashboard.learning",
            "learning_signal_count": "dashboard.learning",
            "learning_fill_count": "dashboard.learning",
            "last_signal_recorded_at": "dashboard.learning",
            "last_fill_recorded_at": "dashboard.learning",
            "safe_mode": "dashboard.recovery",
            "hard_stop": "dashboard.recovery",
            "trading_ready": "dashboard.recovery",
            "failure_stage": "dashboard.recovery",
            "last_restart_detected_at": "dashboard.recovery",
            "last_recovery_completed_at": "dashboard.recovery",
            "promotion_ready": "dashboard.promotion",
            "last_promotion_reviewed_at": "dashboard.promotion",
        }
        if metric_key in {"updated_at", "age_sec", "freshness_window_sec"}:
            freshness_url_keys = {
                "trading": "dashboard.market",
                "learning": "dashboard.learning",
                "recovery": "dashboard.recovery",
                "promotion": "dashboard.promotion",
            }
            return freshness_url_keys[section_key]
        return metric_url_keys[metric_key]

    @staticmethod
    def _resolve_metric_action_tab_key(
        *,
        section_key: str,
        metric_key: str,
    ) -> str:
        metric_tab_keys = {
            "buy_count": "timeline",
            "sell_count": "timeline",
            "stop_loss_count": "history",
            "realized_pnl": "timeline",
            "unrealized_pnl": "current",
            "recent_stop_loss_reason": "history",
            "last_learning_event": "recent-events",
            "learning_signal_count": "recent-events",
            "learning_fill_count": "recent-events",
            "last_signal_recorded_at": "recent-events",
            "last_fill_recorded_at": "recent-events",
            "safe_mode": "status",
            "hard_stop": "status",
            "trading_ready": "status",
            "failure_stage": "status",
            "last_restart_detected_at": "timeline",
            "last_recovery_completed_at": "timeline",
            "promotion_ready": "status",
            "last_promotion_reviewed_at": "status",
        }
        if metric_key in {"updated_at", "age_sec", "freshness_window_sec"}:
            freshness_tab_keys = {
                "trading": "overview",
                "learning": "recent-events",
                "recovery": "status",
                "promotion": "status",
            }
            return freshness_tab_keys[section_key]
        return metric_tab_keys[metric_key]

    @staticmethod
    def _resolve_metric_action_target(
        *,
        section_key: str,
        metric_key: str,
    ) -> str:
        metric_targets = {
            "buy_count": "execution_timeline",
            "sell_count": "execution_timeline",
            "stop_loss_count": "position_history",
            "realized_pnl": "execution_timeline",
            "unrealized_pnl": "current_position",
            "recent_stop_loss_reason": "position_history",
            "last_learning_event": "learning_recent_events",
            "learning_signal_count": "learning_recent_events",
            "learning_fill_count": "learning_recent_events",
            "last_signal_recorded_at": "learning_recent_events",
            "last_fill_recorded_at": "learning_recent_events",
            "safe_mode": "recovery_status",
            "hard_stop": "recovery_status",
            "trading_ready": "recovery_status",
            "failure_stage": "recovery_status",
            "last_restart_detected_at": "recovery_timeline",
            "last_recovery_completed_at": "recovery_timeline",
            "promotion_ready": "promotion_status",
            "last_promotion_reviewed_at": "promotion_status",
        }
        if metric_key in {"updated_at", "age_sec", "freshness_window_sec"}:
            freshness_targets = {
                "trading": "market_overview",
                "learning": "learning_recent_events",
                "recovery": "recovery_status",
                "promotion": "promotion_status",
            }
            return freshness_targets[section_key]
        return metric_targets[metric_key]

    @staticmethod
    def _resolve_metric_action_params(
        *,
        section_key: str,
        metric_key: str,
    ) -> dict[str, object]:
        metric_params = {
            "buy_count": {"focus_metric": "buy_count"},
            "sell_count": {"focus_metric": "sell_count"},
            "stop_loss_count": {"focus_metric": "stop_loss_count", "highlight_reason": True},
            "realized_pnl": {"focus_metric": "realized_pnl"},
            "unrealized_pnl": {"focus_metric": "unrealized_pnl"},
            "recent_stop_loss_reason": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True},
            "last_learning_event": {"focus_metric": "last_learning_event"},
            "learning_signal_count": {"focus_metric": "learning_signal_count", "event_type": "signal"},
            "learning_fill_count": {"focus_metric": "learning_fill_count", "event_type": "fill"},
            "last_signal_recorded_at": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"},
            "last_fill_recorded_at": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"},
            "safe_mode": {"focus_metric": "safe_mode"},
            "hard_stop": {"focus_metric": "hard_stop"},
            "trading_ready": {"focus_metric": "trading_ready"},
            "failure_stage": {"focus_metric": "failure_stage"},
            "last_restart_detected_at": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"},
            "last_recovery_completed_at": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"},
            "promotion_ready": {"focus_metric": "promotion_ready"},
            "last_promotion_reviewed_at": {"focus_metric": "last_promotion_reviewed_at"},
        }
        if metric_key in {"updated_at", "age_sec", "freshness_window_sec"}:
            return {
                "focus_metric": metric_key,
                "section": section_key,
                "kind": "freshness",
            }
        return metric_params[metric_key]

    @staticmethod
    def _build_metric_action_route(
        *,
        section_key: str,
        metric_key: str,
    ) -> dict[str, object]:
        return {
            "url_key": DashboardSummaryFacade._resolve_metric_action_url_key(
                section_key=section_key,
                metric_key=metric_key,
            ),
            "tab_key": DashboardSummaryFacade._resolve_metric_action_tab_key(
                section_key=section_key,
                metric_key=metric_key,
            ),
            "target": DashboardSummaryFacade._resolve_metric_action_target(
                section_key=section_key,
                metric_key=metric_key,
            ),
            "params": DashboardSummaryFacade._resolve_metric_action_params(
                section_key=section_key,
                metric_key=metric_key,
            ),
        }

    @staticmethod
    def _build_section_freshness_metric_items(
        *,
        section_key: str,
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
                "recommended_action": DashboardSummaryFacade._resolve_metric_recommended_action(
                    key="updated_at",
                    value=updated_at,
                ),
                "recommended_action_label": DashboardSummaryFacade._resolve_metric_recommended_action_label(
                    key="updated_at",
                    value=updated_at,
                ),
                "action_group": DashboardSummaryFacade._resolve_metric_action_group(
                    DashboardSummaryFacade._resolve_metric_recommended_action_label(
                        key="updated_at",
                        value=updated_at,
                    )
                ),
                "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="updated_at",
                            value=updated_at,
                        )
                    )
                ),
                "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="updated_at",
                            value=updated_at,
                        )
                    )
                ),
                "action_url_key": DashboardSummaryFacade._resolve_metric_action_url_key(
                    section_key=section_key,
                    metric_key="updated_at",
                ),
                "action_tab_key": DashboardSummaryFacade._resolve_metric_action_tab_key(
                    section_key=section_key,
                    metric_key="updated_at",
                ),
                "action_target": DashboardSummaryFacade._resolve_metric_action_target(
                    section_key=section_key,
                    metric_key="updated_at",
                ),
                "action_params": DashboardSummaryFacade._resolve_metric_action_params(
                    section_key=section_key,
                    metric_key="updated_at",
                ),
                "action_route": DashboardSummaryFacade._build_metric_action_route(
                    section_key=section_key,
                    metric_key="updated_at",
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
                "recommended_action": DashboardSummaryFacade._resolve_metric_recommended_action(
                    key="age_sec",
                    value=age_sec,
                ),
                "recommended_action_label": DashboardSummaryFacade._resolve_metric_recommended_action_label(
                    key="age_sec",
                    value=age_sec,
                ),
                "action_group": DashboardSummaryFacade._resolve_metric_action_group(
                    DashboardSummaryFacade._resolve_metric_recommended_action_label(
                        key="age_sec",
                        value=age_sec,
                    )
                ),
                "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="age_sec",
                            value=age_sec,
                        )
                    )
                ),
                "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="age_sec",
                            value=age_sec,
                        )
                    )
                ),
                "action_url_key": DashboardSummaryFacade._resolve_metric_action_url_key(
                    section_key=section_key,
                    metric_key="age_sec",
                ),
                "action_tab_key": DashboardSummaryFacade._resolve_metric_action_tab_key(
                    section_key=section_key,
                    metric_key="age_sec",
                ),
                "action_target": DashboardSummaryFacade._resolve_metric_action_target(
                    section_key=section_key,
                    metric_key="age_sec",
                ),
                "action_params": DashboardSummaryFacade._resolve_metric_action_params(
                    section_key=section_key,
                    metric_key="age_sec",
                ),
                "action_route": DashboardSummaryFacade._build_metric_action_route(
                    section_key=section_key,
                    metric_key="age_sec",
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
                "recommended_action": DashboardSummaryFacade._resolve_metric_recommended_action(
                    key="freshness_window_sec",
                    value=freshness_window_sec,
                ),
                "recommended_action_label": DashboardSummaryFacade._resolve_metric_recommended_action_label(
                    key="freshness_window_sec",
                    value=freshness_window_sec,
                ),
                "action_group": DashboardSummaryFacade._resolve_metric_action_group(
                    DashboardSummaryFacade._resolve_metric_recommended_action_label(
                        key="freshness_window_sec",
                        value=freshness_window_sec,
                    )
                ),
                "action_priority": DashboardSummaryFacade._resolve_metric_action_priority(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="freshness_window_sec",
                            value=freshness_window_sec,
                        )
                    )
                ),
                "actionable": DashboardSummaryFacade._resolve_metric_actionable(
                    DashboardSummaryFacade._resolve_metric_action_group(
                        DashboardSummaryFacade._resolve_metric_recommended_action_label(
                            key="freshness_window_sec",
                            value=freshness_window_sec,
                        )
                    )
                ),
                "action_url_key": DashboardSummaryFacade._resolve_metric_action_url_key(
                    section_key=section_key,
                    metric_key="freshness_window_sec",
                ),
                "action_tab_key": DashboardSummaryFacade._resolve_metric_action_tab_key(
                    section_key=section_key,
                    metric_key="freshness_window_sec",
                ),
                "action_target": DashboardSummaryFacade._resolve_metric_action_target(
                    section_key=section_key,
                    metric_key="freshness_window_sec",
                ),
                "action_params": DashboardSummaryFacade._resolve_metric_action_params(
                    section_key=section_key,
                    metric_key="freshness_window_sec",
                ),
                "action_route": DashboardSummaryFacade._build_metric_action_route(
                    section_key=section_key,
                    metric_key="freshness_window_sec",
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
