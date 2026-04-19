from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.market.store import MarketPriceStore
from app.services.position.store import CurrentPositionStore
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState
from app.services.risk.stop_loss import PositionSnapshot


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


def test_dashboard_summary_facade_includes_execution_ledger_stats() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=100.0,
            fee=34.12,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=805.0,
            filled_quantity=100.0,
            fee=33.5,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=True,
        ),
        reason_code="STOP_LOSS_PRICE_HIT",
    )
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        execution_ledger=ledger,
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload["buy_count"] == 1
    assert payload["sell_count"] == 1
    assert payload["stop_loss_count"] == 1
    assert payload["recent_stop_loss_reason"] == "STOP_LOSS_PRICE_HIT"
    assert payload["realized_pnl"] < 0.0


def test_dashboard_summary_facade_includes_unrealized_pnl_from_latest_price() -> None:
    position_store = CurrentPositionStore()
    position_store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    market_price_store = MarketPriceStore()
    market_price_store.save(market="KRW-XRP", price=845.0)
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        position_store=position_store,
        market_price_store=market_price_store,
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=100.0,
            avg_buy_price=820.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload["unrealized_pnl"] == 2500.0
