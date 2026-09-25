"""Shared realized return calculations for the dashboard, Telegram, and reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))
DAILY_GOAL_RETURN_RATE = 0.001  # +0.10%
DAILY_GOAL_WINDOW = timedelta(hours=24)


def calculate_daily_goal_progress(
    records: list[Any],
    *,
    initial_capital: float,
    now: datetime | None = None,
) -> dict[str, float | int | bool]:
    """Return progress on net realized PnL for the last 24 hours."""
    current_time = _as_aware(now or datetime.now(KST))
    capital = max(float(initial_capital or 0.0), 0.0)
    performance = calculate_period_realized_performance(
        records,
        start=current_time - DAILY_GOAL_WINDOW,
        end=current_time,
    )
    realized_pnl = float(performance["realized_pnl"])
    target_profit = capital * DAILY_GOAL_RETURN_RATE
    return_rate = 0.0 if capital <= 0 else realized_pnl / capital
    progress_pct = 0.0 if target_profit <= 0 else realized_pnl / target_profit * 100.0
    return {
        **performance,
        "target_return_rate": DAILY_GOAL_RETURN_RATE,
        "initial_capital": round(capital, 2),
        "target_profit": round(target_profit, 2),
        "return_rate": round(return_rate, 8),
        "progress_pct": round(progress_pct, 2),
        "remaining_profit": round(max(target_profit - realized_pnl, 0.0), 2),
        "available": capital > 0,
        "goal_reached": capital > 0 and realized_pnl >= target_profit,
    }


def calculate_period_realized_performance(
    records: list[Any],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, float | int | None]:
    """Calculate net closed-trade return in a time window from full cost basis.

    Buy fills outside the window are retained to reconstruct average cost, but
    only sells inside [start, end) count toward the period's performance.
    """
    start_time = _as_aware(start)
    end_time = _as_aware(end)
    open_quantity = 0.0
    average_unit_cost = 0.0
    realized_pnl = 0.0
    closed_cost_basis = 0.0
    stop_loss_pnl = 0.0
    regular_sell_pnl = 0.0
    sell_count = stop_loss_count = regular_sell_count = 0
    win_count = loss_count = 0

    ordered_records = sorted(
        records,
        key=lambda row: _record_time(row) or datetime.min.replace(tzinfo=timezone.utc),
    )
    for record in ordered_records:
        fill = getattr(record, "fill", None)
        if fill is None or getattr(fill, "status", None) != "filled":
            continue
        quantity = max(float(getattr(fill, "filled_quantity", 0.0) or 0.0), 0.0)
        price = max(float(getattr(fill, "filled_price", 0.0) or 0.0), 0.0)
        fee = max(float(getattr(fill, "fee", 0.0) or 0.0), 0.0)
        if quantity <= 0 or price <= 0:
            continue

        if getattr(fill, "side", None) == "buy":
            total_cost = (average_unit_cost * open_quantity) + (price * quantity) + fee
            open_quantity += quantity
            average_unit_cost = total_cost / open_quantity if open_quantity > 0 else 0.0
            continue
        if getattr(fill, "side", None) != "sell":
            continue

        matched_quantity = min(open_quantity, quantity)
        if matched_quantity <= 0:
            continue
        recorded_at = _record_time(record)
        if recorded_at is not None and start_time <= recorded_at < end_time:
            allocated_sell_fee = fee * matched_quantity / quantity
            cost_basis = average_unit_cost * matched_quantity
            pnl = (price * matched_quantity) - allocated_sell_fee - cost_basis
            realized_pnl += pnl
            closed_cost_basis += cost_basis
            sell_count += 1
            if pnl > 0:
                win_count += 1
            else:
                loss_count += 1
            if getattr(fill, "is_stop_loss", False):
                stop_loss_pnl += pnl
                stop_loss_count += 1
            else:
                regular_sell_pnl += pnl
                regular_sell_count += 1
        open_quantity = max(open_quantity - matched_quantity, 0.0)
        if open_quantity <= 1e-12:
            open_quantity = 0.0
            average_unit_cost = 0.0

    return_rate = None if closed_cost_basis <= 0 else realized_pnl / closed_cost_basis
    return {
        "realized_pnl": round(realized_pnl, 2),
        "closed_cost_basis": round(closed_cost_basis, 2),
        "closed_return_rate": None if return_rate is None else round(return_rate, 8),
        "stop_loss_pnl": round(stop_loss_pnl, 2),
        "regular_sell_pnl": round(regular_sell_pnl, 2),
        "stop_loss_count": stop_loss_count,
        "regular_sell_count": regular_sell_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "sell_count": sell_count,
    }


def progress_bar(progress_pct: float, *, width: int = 10) -> str:
    """Format a compact text progress bar for Telegram."""
    filled = round(min(max(float(progress_pct), 0.0), 100.0) / 100.0 * width)
    return "▰" * filled + "▱" * (width - filled)


def _record_time(record: Any) -> datetime | None:
    value = getattr(record, "recorded_at", None)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return None
    return _as_aware(parsed) if isinstance(parsed, datetime) else None


def _as_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=KST) if value.tzinfo is None else value.astimezone(timezone.utc)
