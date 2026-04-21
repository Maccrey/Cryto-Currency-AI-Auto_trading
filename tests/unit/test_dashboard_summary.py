from __future__ import annotations

from app.services.dashboard.summary import DashboardSummary, DashboardSummaryService
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState


def test_dashboard_summary_service_builds_summary_from_boot_state() -> None:
    service = DashboardSummaryService()
    boot_state = BootState(
        safe_mode=True,
        hard_stop=True,
        trading_ready=False,
        failure_stage="open_order_reconcile",
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=180.5,
            avg_buy_price=815.0,
        ),
        reconcile_result={"open_order_count": 2},
    )

    summary = service.build(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
        realized_pnl=12500.0,
        unrealized_pnl=-3200.0,
        buy_count=4,
        sell_count=3,
        stop_loss_count=1,
        recent_stop_loss_reason="STOP_LOSS_PRICE_HIT",
        last_learning_event=None,
        learning_signal_count=0,
        learning_fill_count=0,
        last_signal_recorded_at=None,
        last_fill_recorded_at=None,
        last_position_event=None,
        last_promotion_reviewed_at=None,
        last_restart_detected_at=None,
        last_recovery_completed_at=None,
        promotion_ready=False,
        section_severity={
            "trading": "critical",
            "learning": "info",
            "recovery": "critical",
            "promotion": "warning",
        },
        section_state_message={
            "trading": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
            "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recovery": "하드스톱이 활성화되어 수동 개입이 필요합니다.",
            "promotion": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
        },
    )

    assert summary == DashboardSummary(
        coin_balance=180.5,
        cash_balance=250000.0,
        realized_pnl=12500.0,
        unrealized_pnl=-3200.0,
        buy_count=4,
        sell_count=3,
        stop_loss_count=1,
        recent_stop_loss_reason="STOP_LOSS_PRICE_HIT",
        trading_mode="demo",
        learning_enabled=True,
        last_learning_event=None,
        learning_signal_count=0,
        learning_fill_count=0,
        last_signal_recorded_at=None,
        last_fill_recorded_at=None,
        last_position_event=None,
        last_promotion_reviewed_at=None,
        last_restart_detected_at=None,
        last_recovery_completed_at=None,
        section_severity={
            "trading": "critical",
            "learning": "info",
            "recovery": "critical",
            "promotion": "warning",
        },
        section_state_message={
            "trading": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
            "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recovery": "하드스톱이 활성화되어 수동 개입이 필요합니다.",
            "promotion": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
        },
        safe_mode=True,
        hard_stop=True,
        trading_ready=False,
        promotion_ready=False,
    )
