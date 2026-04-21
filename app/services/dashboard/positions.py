from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.position.ledger import PositionLifecycleRecord


@dataclass(frozen=True)
class DashboardPositionEntry:
    event_type: str
    severity: str
    state_message: str
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
                severity=self._derive_severity(record),
                state_message=self._derive_state_message(record),
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

    @staticmethod
    def _derive_severity(record: PositionLifecycleRecord) -> str:
        if record.event_type == "opened":
            return "info"
        if record.event_type == "reduced":
            return "warning"
        if record.reason_code and record.reason_code.startswith("STOP_LOSS"):
            return "critical"
        return "info"

    @staticmethod
    def _derive_state_message(record: PositionLifecycleRecord) -> str:
        if record.event_type == "opened":
            return "포지션 진입이 완료되었습니다."
        if record.event_type == "reduced":
            return "포지션이 부분 청산되었습니다."
        if record.reason_code and record.reason_code.startswith("STOP_LOSS"):
            return "손절 조건 충족으로 포지션이 종료되었습니다."
        if record.event_type == "closed":
            return "포지션이 종료되었습니다."
        return "포지션 이벤트가 기록되었습니다."
