from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReentryBlockDecision:
    allowed: bool
    remaining_seconds: int
    reason_code: str | None


@dataclass(frozen=True)
class FixedCooldownReentryPolicy:
    """Calculate a fixed cooldown window after a stop-loss event."""

    block_seconds: int

    def remaining_seconds(self, *, last_triggered_at: int, now: int) -> int:
        return max(self.block_seconds - (now - last_triggered_at), 0)


class ReentryBlocker:
    """Prevent immediate re-entry after a stop-loss exit on the same market."""

    def __init__(
        self,
        *,
        block_seconds: int | None = None,
        cooldown_policy: FixedCooldownReentryPolicy | None = None,
    ) -> None:
        if cooldown_policy is None:
            if block_seconds is None:
                raise ValueError("block_seconds or cooldown_policy is required")
            cooldown_policy = FixedCooldownReentryPolicy(block_seconds=block_seconds)
        self._cooldown_policy = cooldown_policy
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

        remaining = self._cooldown_policy.remaining_seconds(
            last_triggered_at=last_triggered_at,
            now=now,
        )
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
