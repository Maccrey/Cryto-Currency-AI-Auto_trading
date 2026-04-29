from __future__ import annotations

from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.status import PromotionStatusSnapshot, PromotionStatusStore


class PromotionStateService:
    """Coordinate latest promotion state and accumulated review history."""

    def __init__(
        self,
        *,
        status_store: PromotionStatusStore | None = None,
        history_store: PromotionHistoryStore | None = None,
    ) -> None:
        self._status_store = status_store or PromotionStatusStore()
        self._history_store = history_store or PromotionHistoryStore()

    def save_review(
        self,
        *,
        market: str,
        reviewed_at: str,
        result: PromotionRunResult,
    ) -> PromotionStatusSnapshot:
        snapshot = self._status_store.save(
            market=market,
            reviewed_at=reviewed_at,
            result=result,
        )
        self._history_store.append(snapshot)
        return snapshot

    def get_latest(self) -> PromotionStatusSnapshot | None:
        return self._status_store.get()

    def list_history(self) -> list[PromotionStatusSnapshot]:
        return self._history_store.list()

    def is_ready_for_review(self) -> bool:
        snapshot = self.get_latest()
        return snapshot is not None and snapshot.evaluation_status == "READY_FOR_REVIEW"

    def build_state_overview(self) -> dict[str, object]:
        snapshot = self.get_latest()
        if snapshot is None:
            return {
                "status": "empty",
                "ready_for_review": False,
                "live_enabled": False,
                "reviewed_at": None,
                "blocking_reason_count": 0,
            }
        return {
            "status": snapshot.evaluation_status,
            "ready_for_review": snapshot.evaluation_status == "READY_FOR_REVIEW",
            "live_enabled": snapshot.live_enabled,
            "reviewed_at": snapshot.reviewed_at,
            "blocking_reason_count": len(snapshot.rejection_reasons),
        }

    def build_review_response(
        self,
        result: PromotionRunResult,
    ) -> dict[str, object]:
        return {
            "status": "ok",
            "evaluation": {
                "status": result.evaluation.status,
                "approved": result.evaluation.approved,
                "rejection_reasons": result.evaluation.rejection_reasons,
            },
            "approval_result": {
                "live_enabled": result.approval_result.live_enabled,
                "safe_mode_entry": result.approval_result.safe_mode_entry,
                "reason_code": result.approval_result.reason_code,
            },
        }

    def build_status_response(self) -> dict[str, object]:
        snapshot = self.get_latest()
        if snapshot is None:
            return {
                "status": "empty",
                "snapshot": None,
            }
        return {
            "status": "ok",
            "snapshot": self.to_payload(snapshot),
        }

    def build_history_response(self) -> dict[str, object]:
        entries = self.list_history()
        if not entries:
            return {
                "status": "empty",
                "history": [],
            }
        return {
            "status": "ok",
            "history": self.to_history_payload(entries),
        }

    @staticmethod
    def to_payload(snapshot: PromotionStatusSnapshot) -> dict[str, object]:
        return PromotionStatusStore.to_payload(snapshot)

    @staticmethod
    def to_history_payload(
        entries: list[PromotionStatusSnapshot],
    ) -> list[dict[str, object]]:
        return PromotionHistoryStore.to_payload(entries)
