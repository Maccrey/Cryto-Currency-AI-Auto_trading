from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.recovery.orchestrator import BootState


@dataclass(frozen=True)
class DashboardSummary:
    coin_balance: float
    cash_balance: float
    realized_pnl: float
    unrealized_pnl: float
    buy_count: int
    sell_count: int
    stop_loss_count: int
    recent_stop_loss_reason: str | None
    trading_mode: str
    learning_enabled: bool
    safe_mode: bool
    trading_ready: bool
    promotion_ready: bool


class DashboardSummaryService:
    """Build the lower-panel summary payload for the dashboard."""

    def build(
        self,
        *,
        boot_state: BootState,
        trading_mode: str,
        learning_enabled: bool,
        realized_pnl: float,
        unrealized_pnl: float,
        buy_count: int,
        sell_count: int,
        stop_loss_count: int,
        recent_stop_loss_reason: str | None,
        promotion_ready: bool,
    ) -> DashboardSummary:
        portfolio = boot_state.portfolio_state
        return DashboardSummary(
            coin_balance=0.0 if portfolio is None else portfolio.asset_balance,
            cash_balance=0.0 if portfolio is None else portfolio.cash_balance,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            buy_count=buy_count,
            sell_count=sell_count,
            stop_loss_count=stop_loss_count,
            recent_stop_loss_reason=recent_stop_loss_reason,
            trading_mode=trading_mode,
            learning_enabled=learning_enabled,
            safe_mode=boot_state.safe_mode,
            trading_ready=boot_state.trading_ready,
            promotion_ready=promotion_ready,
        )

    @staticmethod
    def to_payload(summary: DashboardSummary) -> dict[str, object]:
        return asdict(summary)
