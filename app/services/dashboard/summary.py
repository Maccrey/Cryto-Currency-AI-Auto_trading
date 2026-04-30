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
    trading_profile: str
    trading_profile_label: str
    learning_enabled: bool
    last_learning_event: str | None
    learning_signal_count: int
    learning_fill_count: int
    last_signal_recorded_at: str | None
    last_fill_recorded_at: str | None
    last_position_event: str | None
    last_promotion_reviewed_at: str | None
    last_restart_detected_at: str | None
    last_recovery_completed_at: str | None
    sections: list[dict[str, object]]
    section_state_label: dict[str, str]
    section_severity: dict[str, str]
    section_state_message: dict[str, str]
    section_recommended_action: dict[str, str]
    safe_mode: bool
    hard_stop: bool
    trading_ready: bool
    promotion_ready: bool


class DashboardSummaryService:
    """Build the lower-panel summary payload for the dashboard."""

    def build(
        self,
        *,
        boot_state: BootState,
        trading_mode: str,
        trading_profile: str,
        trading_profile_label: str,
        learning_enabled: bool,
        realized_pnl: float,
        unrealized_pnl: float,
        buy_count: int,
        sell_count: int,
        stop_loss_count: int,
        recent_stop_loss_reason: str | None,
        last_learning_event: str | None,
        learning_signal_count: int,
        learning_fill_count: int,
        last_signal_recorded_at: str | None,
        last_fill_recorded_at: str | None,
        last_position_event: str | None,
        last_promotion_reviewed_at: str | None,
        last_restart_detected_at: str | None,
        last_recovery_completed_at: str | None,
        sections: list[dict[str, object]],
        section_state_label: dict[str, str],
        section_severity: dict[str, str],
        section_state_message: dict[str, str],
        section_recommended_action: dict[str, str],
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
            trading_profile=trading_profile,
            trading_profile_label=trading_profile_label,
            learning_enabled=learning_enabled,
            last_learning_event=last_learning_event,
            learning_signal_count=learning_signal_count,
            learning_fill_count=learning_fill_count,
            last_signal_recorded_at=last_signal_recorded_at,
            last_fill_recorded_at=last_fill_recorded_at,
            last_position_event=last_position_event,
            last_promotion_reviewed_at=last_promotion_reviewed_at,
            last_restart_detected_at=last_restart_detected_at,
            last_recovery_completed_at=last_recovery_completed_at,
            sections=sections,
            section_state_label=section_state_label,
            section_severity=section_severity,
            section_state_message=section_state_message,
            section_recommended_action=section_recommended_action,
            safe_mode=boot_state.safe_mode,
            hard_stop=boot_state.hard_stop,
            trading_ready=boot_state.trading_ready,
            promotion_ready=promotion_ready,
        )

    @staticmethod
    def to_payload(summary: DashboardSummary) -> dict[str, object]:
        return asdict(summary)
