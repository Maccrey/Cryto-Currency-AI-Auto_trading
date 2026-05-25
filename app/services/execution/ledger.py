from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.services.execution.demo import FillResult
from app.services.portfolio.sync import PortfolioState


@dataclass(frozen=True)
class ExecutionLedgerRecord:
    fill: FillResult
    reason_code: str | None
    recorded_at: str | None
    signal_level: str | None = None
    signal_score: float | None = None
    market_state: str | None = None
    market_state_label: str | None = None
    box_range_low: float | None = None
    box_range_high: float | None = None


@dataclass(frozen=True)
class ExecutionLedgerSummary:
    realized_pnl: float
    buy_count: int
    sell_count: int
    stop_loss_count: int
    recent_stop_loss_reason: str | None


@dataclass(frozen=True)
class ExecutionPerformanceProfile:
    realized_pnl: float
    regular_sell_pnl: float
    stop_loss_pnl: float
    buy_count: int
    weak_buy_count: int
    sell_count: int
    stop_loss_count: int
    weak_buy_ratio: float
    stop_loss_to_profit_ratio: float
    recent_stop_loss_reason: str | None


class ExecutionLedger:
    """Track fill history for runtime dashboard summaries."""

    def __init__(self, *, storage_path: Path | None = None) -> None:
        self._storage_path = storage_path
        self._records: list[ExecutionLedgerRecord] = []
        self._load()

    def record_fill(
        self,
        fill: FillResult,
        *,
        reason_code: str | None = None,
        recorded_at: str | None = None,
        signal_level: str | None = None,
        signal_score: float | None = None,
        market_state: object | None = None,
        market_state_label: object | None = None,
        box_range_low: object | None = None,
        box_range_high: object | None = None,
    ) -> None:
        self._records.append(
            ExecutionLedgerRecord(
                fill=fill,
                reason_code=reason_code,
                recorded_at=recorded_at or datetime.now().astimezone().isoformat(timespec="seconds"),
                signal_level=signal_level,
                signal_score=signal_score,
                market_state=None if market_state is None else str(market_state),
                market_state_label=None if market_state_label is None else str(market_state_label),
                box_range_low=self._optional_float(box_range_low),
                box_range_high=self._optional_float(box_range_high),
            ),
        )
        self._persist()

    def list_records(self) -> list[ExecutionLedgerRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()
        self._persist()

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

    def performance_profile(self) -> ExecutionPerformanceProfile:
        buy_count = 0
        weak_buy_count = 0
        sell_count = 0
        stop_loss_count = 0
        recent_stop_loss_reason = None
        realized_pnl = 0.0
        regular_sell_pnl = 0.0
        stop_loss_pnl = 0.0
        open_quantity = 0.0
        average_cost = 0.0

        for record in self._records:
            fill = record.fill
            if fill.status != "filled":
                continue

            if fill.side == "buy":
                buy_count += 1
                if record.signal_level == "weak":
                    weak_buy_count += 1
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
            pnl = proceeds - (average_cost * matched_quantity)
            realized_pnl += pnl
            if fill.is_stop_loss:
                stop_loss_pnl += pnl
            else:
                regular_sell_pnl += pnl
            open_quantity = round(open_quantity - matched_quantity, 8)
            if open_quantity <= 0:
                open_quantity = 0.0
                average_cost = 0.0

        weak_buy_ratio = 0.0 if buy_count <= 0 else weak_buy_count / buy_count
        profitable_sell_pnl = max(regular_sell_pnl, 0.0)
        stop_loss_to_profit_ratio = (
            abs(stop_loss_pnl) / profitable_sell_pnl
            if profitable_sell_pnl > 0
            else (float("inf") if stop_loss_pnl < 0 else 0.0)
        )
        return ExecutionPerformanceProfile(
            realized_pnl=round(realized_pnl, 2),
            regular_sell_pnl=round(regular_sell_pnl, 2),
            stop_loss_pnl=round(stop_loss_pnl, 2),
            buy_count=buy_count,
            weak_buy_count=weak_buy_count,
            sell_count=sell_count,
            stop_loss_count=stop_loss_count,
            weak_buy_ratio=round(weak_buy_ratio, 4),
            stop_loss_to_profit_ratio=round(stop_loss_to_profit_ratio, 4),
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

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return
        restored: list[ExecutionLedgerRecord] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            fill_payload = item.get("fill")
            if not isinstance(fill_payload, dict):
                continue
            try:
                restored.append(
                    ExecutionLedgerRecord(
                        fill=FillResult(
                            market=str(fill_payload.get("market", "")),
                            side=str(fill_payload.get("side", "")),
                            filled_price=float(fill_payload.get("filled_price", 0.0)),
                            filled_quantity=float(fill_payload.get("filled_quantity", 0.0)),
                            fee=float(fill_payload.get("fee", 0.0)),
                            status=str(fill_payload.get("status", "")),
                            mode=str(fill_payload.get("mode", "")),
                            is_virtual=bool(fill_payload.get("is_virtual")),
                            is_stop_loss=bool(fill_payload.get("is_stop_loss")),
                        ),
                        reason_code=None if item.get("reason_code") is None else str(item.get("reason_code")),
                        recorded_at=None if item.get("recorded_at") is None else str(item.get("recorded_at")),
                        signal_level=None if item.get("signal_level") is None else str(item.get("signal_level")),
                        signal_score=self._optional_float(item.get("signal_score")),
                        market_state=None if item.get("market_state") is None else str(item.get("market_state")),
                        market_state_label=None if item.get("market_state_label") is None else str(item.get("market_state_label")),
                        box_range_low=self._optional_float(item.get("box_range_low")),
                        box_range_high=self._optional_float(item.get("box_range_high")),
                    ),
                )
            except (TypeError, ValueError):
                continue
        self._records = restored

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [
                {
                    "fill": asdict(record.fill),
                    "reason_code": record.reason_code,
                    "recorded_at": record.recorded_at,
                    "signal_level": record.signal_level,
                    "signal_score": record.signal_score,
                    "market_state": record.market_state,
                    "market_state_label": record.market_state_label,
                    "box_range_low": record.box_range_low,
                    "box_range_high": record.box_range_high,
                }
                for record in self._records
            ],
        }
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
