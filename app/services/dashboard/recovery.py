from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.learning.service import LearningEvent
from app.services.recovery.orchestrator import BootState


@dataclass(frozen=True)
class DashboardRecovery:
    safe_mode: bool
    hard_stop: bool
    trading_ready: bool
    failure_stage: str | None
    restart_count: int | None
    blocked_reason: str | None
    last_restart_detected_at: str | None
    last_recovery_completed_at: str | None
    hard_stop_triggered_at: str | None
    recent_events: list[dict[str, object]]
    recent_recovery_timeline: list[dict[str, object]]
    recent_hard_stop_events: list[dict[str, object]]
    recent_hard_stop_timeline: list[dict[str, object]]
    recovery_timeline: list[dict[str, object]]
    current_state_summary: dict[str, object]


class DashboardRecoveryService:
    """Build dashboard-friendly recovery state payloads."""

    RECOVERY_EVENT_NAMES = {"restart_detected", "recovery_completed"}
    HARD_STOP_EVENT_NAMES = {"hard_stop_triggered"}

    def build(
        self,
        *,
        boot_state: BootState,
        events: list[LearningEvent],
    ) -> DashboardRecovery:
        reconcile_result = boot_state.reconcile_result or {}
        last_restart_detected_at = next(
            (
                event.recorded_at
                for event in reversed(events)
                if event.event_name == "restart_detected"
            ),
            None,
        )
        last_recovery_completed_at = next(
            (
                event.recorded_at
                for event in reversed(events)
                if event.event_name == "recovery_completed"
            ),
            None,
        )
        hard_stop_triggered_at = next(
            (
                event.recorded_at
                for event in reversed(events)
                if event.event_name == "hard_stop_triggered"
            ),
            None,
        )
        recent_events = [
            asdict(event)
            for event in events
            if event.event_name in self.RECOVERY_EVENT_NAMES
        ]
        recent_recovery_timeline = [
            {
                "event_name": event.event_name,
                "occurred_at": event.recorded_at,
                "app_name": event.payload.get("app_name"),
                "trading_mode": event.payload.get("trading_mode"),
                "safe_mode": event.payload.get("safe_mode"),
                "trading_ready": event.payload.get("trading_ready"),
                "failure_stage": event.payload.get("failure_stage"),
                "open_order_count": event.payload.get("open_order_count"),
            }
            for event in events
            if event.event_name in self.RECOVERY_EVENT_NAMES
        ]
        recent_hard_stop_events = [
            asdict(event)
            for event in events
            if event.event_name in self.HARD_STOP_EVENT_NAMES
        ]
        recent_hard_stop_timeline = [
            {
                "event_name": event.event_name,
                "triggered_at": event.recorded_at,
                "restart_count": event.payload.get("restart_count"),
                "blocked_reason": event.payload.get("blocked_reason"),
            }
            for event in events
            if event.event_name in self.HARD_STOP_EVENT_NAMES
        ]
        recovery_timeline = sorted(
            [
                {
                    "event_name": event["event_name"],
                    "occurred_at": event["occurred_at"],
                    "app_name": event["app_name"],
                    "trading_mode": event["trading_mode"],
                    "safe_mode": event["safe_mode"],
                    "trading_ready": event["trading_ready"],
                    "failure_stage": event["failure_stage"],
                    "open_order_count": event["open_order_count"],
                    "restart_count": None,
                    "blocked_reason": None,
                }
                for event in recent_recovery_timeline
            ]
            + [
                {
                    "event_name": event["event_name"],
                    "occurred_at": event["triggered_at"],
                    "app_name": None,
                    "trading_mode": None,
                    "safe_mode": None,
                    "trading_ready": None,
                    "failure_stage": "hard_stop",
                    "open_order_count": None,
                    "restart_count": event["restart_count"],
                    "blocked_reason": event["blocked_reason"],
                }
                for event in recent_hard_stop_timeline
            ],
            key=lambda event: str(event["occurred_at"]),
        )
        current_state_summary = {
            "safe_mode": boot_state.safe_mode,
            "hard_stop": boot_state.hard_stop,
            "trading_ready": boot_state.trading_ready,
            "failure_stage": boot_state.failure_stage,
            "restart_count": reconcile_result.get("restart_count"),
            "blocked_reason": reconcile_result.get("blocked_reason"),
            "last_restart_detected_at": last_restart_detected_at,
            "last_recovery_completed_at": last_recovery_completed_at,
            "hard_stop_triggered_at": hard_stop_triggered_at,
        }
        return DashboardRecovery(
            safe_mode=boot_state.safe_mode,
            hard_stop=boot_state.hard_stop,
            trading_ready=boot_state.trading_ready,
            failure_stage=boot_state.failure_stage,
            restart_count=reconcile_result.get("restart_count"),
            blocked_reason=reconcile_result.get("blocked_reason"),
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            hard_stop_triggered_at=hard_stop_triggered_at,
            recent_events=recent_events,
            recent_recovery_timeline=recent_recovery_timeline,
            recent_hard_stop_events=recent_hard_stop_events,
            recent_hard_stop_timeline=recent_hard_stop_timeline,
            recovery_timeline=recovery_timeline,
            current_state_summary=current_state_summary,
        )

    @staticmethod
    def to_payload(recovery: DashboardRecovery) -> dict[str, object]:
        return asdict(recovery)
