from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime

from app.services.risk.stop_loss import PositionSnapshot


@dataclass(frozen=True)
class PositionLifecycleRecord:
    event_type: str
    market: str
    signal_level: str
    entry_price: float
    quantity: float
    stop_loss_price: float
    reason_code: str | None
    recorded_at: str


class PositionLifecycleLedger:
    """Track position lifecycle events for dashboard history."""

    def __init__(
        self,
        *,
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self._timestamp_provider = timestamp_provider or (
            lambda: datetime.now().astimezone().isoformat()
        )
        self._records: list[PositionLifecycleRecord] = []

    def record(
        self,
        *,
        event_type: str,
        position: PositionSnapshot,
        reason_code: str | None = None,
    ) -> PositionLifecycleRecord:
        record = PositionLifecycleRecord(
            event_type=event_type,
            market=position.market,
            signal_level=position.signal_level,
            entry_price=position.entry_price,
            quantity=position.quantity,
            stop_loss_price=position.stop_loss_price,
            reason_code=reason_code,
            recorded_at=self._timestamp_provider(),
        )
        self._records.append(record)
        return record

    def list_records(self, *, limit: int | None = None) -> list[PositionLifecycleRecord]:
        if limit is None or limit >= len(self._records):
            return list(self._records)
        return self._records[-limit:]

    @staticmethod
    def to_payload(record: PositionLifecycleRecord) -> dict[str, object]:
        return asdict(record)
