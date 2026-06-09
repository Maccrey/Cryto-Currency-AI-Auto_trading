from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque


@dataclass(frozen=True)
class MarketStateEntryDecision:
    allowed: bool
    reason_code: str | None
    transition_boost: bool
    previous_market_state: str | None
    current_market_state: str
    current_state_count: int
    transition: str | None


class MarketStateEntryGuard:
    """Gate entries using price-card market state and confirmed state transitions."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        confirmation_ticks: int = 2,
        bear_entry_min_score: float = 0.65,
    ) -> None:
        self._enabled = enabled
        self._confirmation_ticks = max(int(confirmation_ticks), 1)
        self._bear_entry_min_score = max(float(bear_entry_min_score), 0.0)
        self._states: Deque[str] = deque(maxlen=max(self._confirmation_ticks * 4, 8))

    def evaluate(
        self,
        *,
        market_state: str,
        signal_level: str,
        signal_score: float,
        entry_type: str = "initial",
        signal_reason_codes: list[str] | None = None,
    ) -> MarketStateEntryDecision:
        current_state = market_state if market_state in {"bull", "box", "bear"} else "box"
        previous_state = self._previous_distinct_state(current_state)
        self._states.append(current_state)
        current_count = self._current_state_count(current_state)
        transition = f"{previous_state}->{current_state}" if previous_state is not None else None
        transition_boost = (
            self._enabled
            and current_state == "bull"
            and previous_state in {"bear", "box"}
            and current_count >= self._confirmation_ticks
        )
        if not self._enabled:
            return MarketStateEntryDecision(
                allowed=True,
                reason_code=None,
                transition_boost=False,
                previous_market_state=previous_state,
                current_market_state=current_state,
                current_state_count=current_count,
                transition=transition,
            )
        if entry_type == "scale_in" and current_state == "bear":
            return MarketStateEntryDecision(
                allowed=False,
                reason_code="MARKET_STATE_BEAR_SCALE_IN_BLOCK",
                transition_boost=False,
                previous_market_state=previous_state,
                current_market_state=current_state,
                current_state_count=current_count,
                transition=transition,
            )
        bear_rebound_participation = (
            entry_type == "initial"
            and signal_level == "medium"
            and signal_score >= 0.4
            and "BEAR_REBOUND_PARTICIPATION" in (signal_reason_codes or [])
        )
        if current_state == "bear" and not bear_rebound_participation and (
            signal_level not in {"strong", "very_strong"} or signal_score < self._bear_entry_min_score
        ):
            return MarketStateEntryDecision(
                allowed=False,
                reason_code="MARKET_STATE_BEAR_ENTRY_BLOCK",
                transition_boost=False,
                previous_market_state=previous_state,
                current_market_state=current_state,
                current_state_count=current_count,
                transition=transition,
            )
        return MarketStateEntryDecision(
            allowed=True,
            reason_code=None,
            transition_boost=transition_boost,
            previous_market_state=previous_state,
            current_market_state=current_state,
            current_state_count=current_count,
            transition=transition,
        )

    def _previous_distinct_state(self, current_state: str) -> str | None:
        for state in reversed(self._states):
            if state != current_state:
                return state
        return None

    def _current_state_count(self, current_state: str) -> int:
        count = 0
        for state in reversed(self._states):
            if state != current_state:
                break
            count += 1
        return count
