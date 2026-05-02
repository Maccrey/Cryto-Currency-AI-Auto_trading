from __future__ import annotations

from dataclasses import dataclass

from app.services.execution.demo import FillResult
from app.services.portfolio.sync import PortfolioState


@dataclass(frozen=True)
class ExecutionLedgerRecord:
    fill: FillResult
    reason_code: str | None


@dataclass(frozen=True)
class ExecutionLedgerSummary:
    realized_pnl: float
    buy_count: int
    sell_count: int
    stop_loss_count: int
    recent_stop_loss_reason: str | None


class ExecutionLedger:
    """Track fill history for runtime dashboard summaries."""

    def __init__(self) -> None:
        self._records: list[ExecutionLedgerRecord] = []

    def record_fill(self, fill: FillResult, *, reason_code: str | None = None) -> None:
        self._records.append(
            ExecutionLedgerRecord(
                fill=fill,
                reason_code=reason_code,
            ),
        )

    def list_records(self) -> list[ExecutionLedgerRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()

    def summarize(self) -> ExecutionLedgerSummary:
        buy_count = 0
        sell_count = 0
        stop_loss_count = 0
        recent_stop_loss_reason = None
        realized_pnl = 0.0
        open_quantity = 0.0
        average_cost = 0.0

        for record in self._records:
            fill = record.fill
            if fill.status != "filled":
                continue

            if fill.side == "buy":
                buy_count += 1
                total_cost = (average_cost * open_quantity) + (fill.filled_price * fill.filled_quantity) + fill.fee
                open_quantity += fill.filled_quantity
                average_cost = 0.0 if open_quantity <= 0 else total_cost / open_quantity
                continue

            sell_count += 1
            if fill.is_stop_loss:
                stop_loss_count += 1
                recent_stop_loss_reason = record.reason_code

            matched_quantity = min(open_quantity, fill.filled_quantity)
            if matched_quantity <= 0:
                continue

            proceeds = (fill.filled_price * matched_quantity) - fill.fee
            realized_pnl += proceeds - (average_cost * matched_quantity)
            open_quantity = round(open_quantity - matched_quantity, 8)
            if open_quantity <= 0:
                open_quantity = 0.0
                average_cost = 0.0

        return ExecutionLedgerSummary(
            realized_pnl=round(realized_pnl, 2),
            buy_count=buy_count,
            sell_count=sell_count,
            stop_loss_count=stop_loss_count,
            recent_stop_loss_reason=recent_stop_loss_reason,
        )

    def portfolio_state(
        self,
        *,
        initial_cash: float,
        asset_currency: str,
    ) -> PortfolioState:
        cash_balance = initial_cash
        asset_balance = 0.0
        average_cost = 0.0

        for record in self._records:
            fill = record.fill
            if fill.status != "filled":
                continue
            gross_amount = fill.filled_price * fill.filled_quantity
            if fill.side == "buy":
                if gross_amount + fill.fee > cash_balance:
                    continue
                total_cost = (average_cost * asset_balance) + gross_amount + fill.fee
                asset_balance += fill.filled_quantity
                cash_balance -= gross_amount + fill.fee
                average_cost = 0.0 if asset_balance <= 0 else total_cost / asset_balance
                continue

            sell_quantity = min(asset_balance, fill.filled_quantity)
            cash_balance += (fill.filled_price * sell_quantity) - fill.fee
            asset_balance = round(asset_balance - sell_quantity, 8)
            if asset_balance <= 0:
                asset_balance = 0.0
                average_cost = 0.0

        return PortfolioState(
            cash_balance=round(cash_balance, 2),
            asset_currency=asset_currency,
            asset_balance=round(asset_balance, 8),
            avg_buy_price=round(average_cost, 8),
        )
