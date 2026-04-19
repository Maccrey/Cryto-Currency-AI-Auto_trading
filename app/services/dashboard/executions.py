from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.execution.ledger import ExecutionLedgerRecord


@dataclass(frozen=True)
class DashboardExecutionEntry:
    market: str
    side: str
    filled_price: float
    filled_quantity: float
    fee: float
    status: str
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
                filled_price=record.fill.filled_price,
                filled_quantity=record.fill.filled_quantity,
                fee=record.fill.fee,
                status=record.fill.status,
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
