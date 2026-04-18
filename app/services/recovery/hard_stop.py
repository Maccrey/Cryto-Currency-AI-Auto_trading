from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HardStopDecision:
    hard_stop: bool
    restart_count: int
    blocked_reason: str | None


class RestartCounter:
    """Track consecutive restarts and enter HARD_STOP past a configured threshold."""

    def __init__(self, *, threshold: int) -> None:
        self._threshold = threshold
        self._restart_count = 0

    def record_restart(self) -> HardStopDecision:
        self._restart_count += 1
        if self._restart_count >= self._threshold:
            return HardStopDecision(
                hard_stop=True,
                restart_count=self._restart_count,
                blocked_reason="RESTART_THRESHOLD_EXCEEDED",
            )

        return HardStopDecision(
            hard_stop=False,
            restart_count=self._restart_count,
            blocked_reason=None,
        )

    def reset(self) -> None:
        self._restart_count = 0
