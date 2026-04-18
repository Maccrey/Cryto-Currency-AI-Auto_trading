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

    @staticmethod
    def to_payload(snapshot: PromotionStatusSnapshot) -> dict[str, object]:
        return PromotionStatusStore.to_payload(snapshot)

    @staticmethod
    def to_history_payload(
        entries: list[PromotionStatusSnapshot],
    ) -> list[dict[str, object]]:
        return PromotionHistoryStore.to_payload(entries)
