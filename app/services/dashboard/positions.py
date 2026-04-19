from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.position.ledger import PositionLifecycleRecord


@dataclass(frozen=True)
class DashboardPositionEntry:
    event_type: str
    market: str
    signal_level: str
    entry_price: float
    quantity: float
    stop_loss_price: float
    reason_code: str | None
    recorded_at: str


class DashboardPositionsService:
    """Build dashboard-friendly position lifecycle payloads."""

    def build_history(
        self,
        records: list[PositionLifecycleRecord],
    ) -> list[DashboardPositionEntry]:
        return [
            DashboardPositionEntry(
                event_type=record.event_type,
                market=record.market,
                signal_level=record.signal_level,
                entry_price=record.entry_price,
                quantity=record.quantity,
                stop_loss_price=record.stop_loss_price,
                reason_code=record.reason_code,
                recorded_at=record.recorded_at,
            )
            for record in records
        ]

    @staticmethod
    def to_history_payload(
        entries: list[DashboardPositionEntry],
    ) -> list[dict[str, object]]:
        return [asdict(entry) for entry in entries]
