from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.promotion.runner import PromotionRunResult


@dataclass(frozen=True)
class PromotionStatusSnapshot:
    market: str
    evaluation_status: str
    approved: bool
    rejection_reasons: list[str]
    live_enabled: bool
    safe_mode_entry: bool
    reason_code: str | None
    reviewed_at: str


class PromotionStatusStore:
    """Keep the latest promotion review result for dashboard and API reads."""

    def __init__(self) -> None:
        self._snapshot: PromotionStatusSnapshot | None = None

    def save(
        self,
        *,
        market: str,
        reviewed_at: str,
        result: PromotionRunResult,
    ) -> PromotionStatusSnapshot:
        snapshot = PromotionStatusSnapshot(
            market=market,
            evaluation_status=result.evaluation.status,
            approved=result.evaluation.approved,
            rejection_reasons=result.evaluation.rejection_reasons,
            live_enabled=result.approval_result.live_enabled,
            safe_mode_entry=result.approval_result.safe_mode_entry,
            reason_code=result.approval_result.reason_code,
            reviewed_at=reviewed_at,
        )
        self._snapshot = snapshot
        return snapshot

    def get(self) -> PromotionStatusSnapshot | None:
        return self._snapshot

    @staticmethod
    def to_payload(snapshot: PromotionStatusSnapshot) -> dict[str, object]:
        return asdict(snapshot)
