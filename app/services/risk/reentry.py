from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReentryBlockDecision:
    allowed: bool
    remaining_seconds: int
    reason_code: str | None


class ReentryBlocker:
    """Prevent immediate re-entry after a stop-loss exit on the same market."""

    def __init__(self, *, block_seconds: int) -> None:
        self._block_seconds = block_seconds
        self._last_stop_loss_at: dict[str, int] = {}

    def record_stop_loss(self, *, market: str, triggered_at: int) -> None:
        self._last_stop_loss_at[market] = triggered_at

    def check(self, *, market: str, now: int) -> ReentryBlockDecision:
        last_triggered_at = self._last_stop_loss_at.get(market)
        if last_triggered_at is None:
            return ReentryBlockDecision(
                allowed=True,
                remaining_seconds=0,
                reason_code=None,
            )

        elapsed = now - last_triggered_at
        remaining = self._block_seconds - elapsed
        if remaining > 0:
            return ReentryBlockDecision(
                allowed=False,
                remaining_seconds=remaining,
                reason_code="REENTRY_BLOCK_ACTIVE",
            )

        return ReentryBlockDecision(
            allowed=True,
            remaining_seconds=0,
            reason_code=None,
        )
