from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReentryBlockDecision:
    allowed: bool
    remaining_seconds: int
    reason_code: str | None
    last_exit_reason_code: str | None = None
    last_exit_price: float | None = None


@dataclass(frozen=True)
class FixedCooldownReentryPolicy:
    """Calculate a fixed cooldown window after a stop-loss event."""

    block_seconds: int

    def remaining_seconds(self, *, last_triggered_at: int, now: int) -> int:
        return max(self.block_seconds - (now - last_triggered_at), 0)


@dataclass(frozen=True)
class AdaptiveCooldownReentryPolicy:
    """Apply different cooldown windows depending on whether the last exit was a profit or loss.

    After a profit exit (익절): a shorter cooldown is applied so the bot can
    re-enter quickly in an ongoing bull market.
    After a stop-loss exit (손절): a longer cooldown is applied to allow the
    market to stabilise before risking capital again.
    """

    profit_block_seconds: int = 60
    loss_block_seconds: int = 120

    def remaining_seconds(
        self,
        *,
        last_triggered_at: int,
        now: int,
        last_exit_reason_code: str | None = None,
    ) -> int:
        is_stop_loss = last_exit_reason_code is not None and str(
            last_exit_reason_code
        ).startswith("STOP_LOSS")
        block = self.loss_block_seconds if is_stop_loss else self.profit_block_seconds
        return max(block - (now - last_triggered_at), 0)


class ReentryBlocker:
    """Prevent immediate re-entry after a recent sell on the same market.

    Supports both ``FixedCooldownReentryPolicy`` (legacy) and the new
    ``AdaptiveCooldownReentryPolicy`` that applies shorter cooldowns after
    profitable exits so the bot can participate in sustained uptrends.
    """

    def __init__(
        self,
        *,
        block_seconds: int | None = None,
        cooldown_policy: FixedCooldownReentryPolicy | AdaptiveCooldownReentryPolicy | None = None,
    ) -> None:
        if cooldown_policy is None:
            if block_seconds is None:
                raise ValueError("block_seconds or cooldown_policy is required")
            cooldown_policy = FixedCooldownReentryPolicy(block_seconds=block_seconds)
        self._cooldown_policy = cooldown_policy
        self._last_stop_loss_at: dict[str, int] = {}
        self._last_exit: dict[str, dict[str, object]] = {}

    def record_stop_loss(self, *, market: str, triggered_at: int) -> None:
        self._last_stop_loss_at[market] = triggered_at

    def record_exit(
        self,
        *,
        market: str,
        side: str,
        reason_code: str | None,
        triggered_at: int,
        price: float | None = None,
    ) -> None:
        if side != "sell":
            return
        self._last_exit[market] = {
            "triggered_at": triggered_at,
            "reason_code": reason_code,
            "price": price,
            "side": side,
        }

    def check(self, *, market: str, now: int, current_price: float | None = None) -> ReentryBlockDecision:
        last_exit = self._last_exit.get(market)
        last_triggered_at = (
            int(last_exit["triggered_at"])
            if last_exit is not None and last_exit.get("triggered_at") is not None
            else self._last_stop_loss_at.get(market)
        )
        if last_triggered_at is None:
            return ReentryBlockDecision(
                allowed=True,
                remaining_seconds=0,
                reason_code=None,
            )

        last_exit_reason_code = (
            None if last_exit is None or last_exit.get("reason_code") is None
            else str(last_exit["reason_code"])
        )

        if isinstance(self._cooldown_policy, AdaptiveCooldownReentryPolicy):
            remaining = self._cooldown_policy.remaining_seconds(
                last_triggered_at=last_triggered_at,
                now=now,
                last_exit_reason_code=last_exit_reason_code,
            )
        else:
            remaining = self._cooldown_policy.remaining_seconds(
                last_triggered_at=last_triggered_at,
                now=now,
            )

        last_exit_price = (
            None
            if last_exit is None or last_exit.get("price") is None
            else float(last_exit["price"])
        )

        if remaining > 0:
            return ReentryBlockDecision(
                allowed=False,
                remaining_seconds=remaining,
                reason_code="REENTRY_BLOCK_AFTER_SELL" if last_exit is not None else "REENTRY_BLOCK_ACTIVE",
                last_exit_reason_code=last_exit_reason_code,
                last_exit_price=last_exit_price,
            )

        return ReentryBlockDecision(
            allowed=True,
            remaining_seconds=0,
            reason_code=None,
            last_exit_reason_code=last_exit_reason_code,
            last_exit_price=last_exit_price,
        )
