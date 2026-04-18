from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.promotion.status import PromotionStatusSnapshot


@dataclass(frozen=True)
class DashboardPromotion:
    market: str
    ready_for_review: bool
    evaluation_status: str
    live_enabled: bool
    safe_mode_entry: bool
    reason_code: str | None
    blocking_reasons: list[str]
    reviewed_at: str


@dataclass(frozen=True)
class DashboardPromotionHistoryEntry:
    market: str
    reviewed_at: str
    evaluation_status: str
    ready_for_review: bool
    live_enabled: bool
    reason_code: str | None


class PromotionDashboardService:
    """Build dashboard-friendly promotion status and history payloads."""

    def build_current(
        self,
        snapshot: PromotionStatusSnapshot | None,
    ) -> DashboardPromotion | None:
        if snapshot is None:
            return None
        return DashboardPromotion(
            market=snapshot.market,
            ready_for_review=snapshot.evaluation_status == "READY_FOR_REVIEW",
            evaluation_status=snapshot.evaluation_status,
            live_enabled=snapshot.live_enabled,
            safe_mode_entry=snapshot.safe_mode_entry,
            reason_code=snapshot.reason_code,
            blocking_reasons=snapshot.rejection_reasons,
            reviewed_at=snapshot.reviewed_at,
        )

    def build_history(
        self,
        entries: list[PromotionStatusSnapshot],
    ) -> list[DashboardPromotionHistoryEntry]:
        return [
            DashboardPromotionHistoryEntry(
                market=entry.market,
                reviewed_at=entry.reviewed_at,
                evaluation_status=entry.evaluation_status,
                ready_for_review=entry.evaluation_status == "READY_FOR_REVIEW",
                live_enabled=entry.live_enabled,
                reason_code=entry.reason_code,
            )
            for entry in entries
        ]

    @staticmethod
    def to_payload(summary: DashboardPromotion) -> dict[str, object]:
        return asdict(summary)

    @staticmethod
    def to_history_payload(
        entries: list[DashboardPromotionHistoryEntry],
    ) -> list[dict[str, object]]:
        return [asdict(entry) for entry in entries]
