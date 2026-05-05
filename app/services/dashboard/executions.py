from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.execution.ledger import ExecutionLedgerRecord


@dataclass(frozen=True)
class DashboardExecutionEntry:
    market: str
    side: str
    side_label: str
    severity: str
    state_message: str
    filled_price: float
    filled_quantity: float
    fee: float
    status: str
    status_label: str
    mode: str
    is_virtual: bool
    is_stop_loss: bool
    reason_code: str | None


class DashboardExecutionsService:
    """Build dashboard-friendly execution timeline payloads."""

    def build_history(
        self,
        records: list[ExecutionLedgerRecord],
    ) -> list[DashboardExecutionEntry]:
        return [
            DashboardExecutionEntry(
                market=record.fill.market,
                side=record.fill.side,
                side_label=self._derive_side_label(record),
                severity=self._derive_severity(record),
                state_message=self._derive_state_message(record),
                filled_price=record.fill.filled_price,
                filled_quantity=record.fill.filled_quantity,
                fee=record.fill.fee,
                status=record.fill.status,
                status_label=self._derive_status_label(record),
                mode=record.fill.mode,
                is_virtual=record.fill.is_virtual,
                is_stop_loss=record.fill.is_stop_loss,
                reason_code=record.reason_code,
            )
            for record in records
        ]

    @staticmethod
    def to_history_payload(
        entries: list[DashboardExecutionEntry],
    ) -> list[dict[str, object]]:
        return [asdict(entry) for entry in entries]

    @staticmethod
    def _derive_severity(record: ExecutionLedgerRecord) -> str:
        if record.fill.is_stop_loss:
            return "critical"
        return "info"

    @staticmethod
    def _derive_state_message(record: ExecutionLedgerRecord) -> str:
        if record.fill.side == "buy":
            return "매수 체결이 완료되었습니다."
        if record.fill.is_stop_loss:
            return "손절 매도 체결이 완료되었습니다."
        return "매도 체결이 완료되었습니다."

    @staticmethod
    def _derive_side_label(record: ExecutionLedgerRecord) -> str:
        if record.fill.side == "buy":
            return "매수"
        if record.fill.is_stop_loss:
            return "손절 매도"
        if record.fill.side == "sell":
            return "매도"
        return record.fill.side

    @staticmethod
    def _derive_status_label(record: ExecutionLedgerRecord) -> str:
        labels = {
            "filled": "체결완료",
            "blocked": "차단됨",
            "wait": "대기",
            "done": "완료",
            "cancel": "취소",
            "cancelled": "취소",
        }
        return labels.get(record.fill.status, record.fill.status)
