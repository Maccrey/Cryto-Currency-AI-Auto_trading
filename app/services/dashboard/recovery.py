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
    recent_hard_stop_events: list[dict[str, object]]
    recent_hard_stop_timeline: list[dict[str, object]]


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
        recent_hard_stop_events = [
            asdict(event)
            for event in events
            if event.event_name in self.HARD_STOP_EVENT_NAMES
        ]
        recent_hard_stop_timeline = [
            {
                "triggered_at": event.recorded_at,
                "restart_count": event.payload.get("restart_count"),
                "blocked_reason": event.payload.get("blocked_reason"),
            }
            for event in events
            if event.event_name in self.HARD_STOP_EVENT_NAMES
        ]
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
            recent_hard_stop_events=recent_hard_stop_events,
            recent_hard_stop_timeline=recent_hard_stop_timeline,
        )

    @staticmethod
    def to_payload(recovery: DashboardRecovery) -> dict[str, object]:
        return asdict(recovery)
