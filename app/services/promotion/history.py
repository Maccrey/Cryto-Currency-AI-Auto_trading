from __future__ import annotations

from dataclasses import asdict

from app.services.promotion.status import PromotionStatusSnapshot


class PromotionHistoryStore:
    """Keep promotion review history in insertion order for runtime inspection."""

    def __init__(self) -> None:
        self._entries: list[PromotionStatusSnapshot] = []

    def append(self, snapshot: PromotionStatusSnapshot) -> PromotionStatusSnapshot:
        self._entries.append(snapshot)
        return snapshot

    def list(self) -> list[PromotionStatusSnapshot]:
        return list(self._entries)

    @staticmethod
    def to_payload(entries: list[PromotionStatusSnapshot]) -> list[dict[str, object]]:
        return [asdict(entry) for entry in entries]
