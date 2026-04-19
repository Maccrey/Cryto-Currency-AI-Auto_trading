from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState


def test_dashboard_summary_facade_builds_payload_with_promotion_state() -> None:
    promotion_state_service = PromotionStateService()
    promotion_state_service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T18:00:00+09:00",
        result=PromotionRunResult(
            evaluation=PromotionEvaluation(
                status="READY_FOR_REVIEW",
                approved=False,
                rejection_reasons=[],
            ),
            approval_result=PromotionApprovalResult(
                live_enabled=True,
                safe_mode_entry=True,
                reason_code=None,
            ),
        ),
    )
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=promotion_state_service,
            promotion_dashboard_service=PromotionDashboardService(),
        ),
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=180.5,
            avg_buy_price=815.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload == {
        "coin_balance": 180.5,
        "cash_balance": 250000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "stop_loss_count": 0,
        "recent_stop_loss_reason": None,
        "trading_mode": "demo",
        "learning_enabled": True,
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "promotion_ready": True,
    }
