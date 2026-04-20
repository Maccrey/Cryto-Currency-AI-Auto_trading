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
    last_restart_detected_at: str | None
    last_recovery_completed_at: str | None
    recent_events: list[dict[str, object]]


class DashboardRecoveryService:
    """Build dashboard-friendly recovery state payloads."""

    RECOVERY_EVENT_NAMES = {"restart_detected", "recovery_completed"}

    def build(
        self,
        *,
        boot_state: BootState,
        events: list[LearningEvent],
    ) -> DashboardRecovery:
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
        recent_events = [
            asdict(event)
            for event in events
            if event.event_name in self.RECOVERY_EVENT_NAMES
        ]
        return DashboardRecovery(
            safe_mode=boot_state.safe_mode,
            hard_stop=boot_state.hard_stop,
            trading_ready=boot_state.trading_ready,
            failure_stage=boot_state.failure_stage,
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            recent_events=recent_events,
        )

    @staticmethod
    def to_payload(recovery: DashboardRecovery) -> dict[str, object]:
        return asdict(recovery)
