from app.services.dashboard.promotion import PromotionDashboardService
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService


def test_dashboard_facade_returns_empty_without_state() -> None:
    facade = PromotionDashboardFacade(
        promotion_state_service=PromotionStateService(),
        promotion_dashboard_service=PromotionDashboardService(),
    )

    assert facade.is_ready_for_review() is False
    assert facade.build_current_response() == {
        "status": "empty",
        "promotion": None,
    }
    assert facade.build_history_response() == {
        "status": "empty",
        "history": [],
    }


def test_dashboard_facade_builds_current_and_history_from_saved_state() -> None:
    state_service = PromotionStateService()
    state_service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T17:00:00+09:00",
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
    facade = PromotionDashboardFacade(
        promotion_state_service=state_service,
        promotion_dashboard_service=PromotionDashboardService(),
    )

    assert facade.is_ready_for_review() is True
    assert facade.build_current_response() == {
        "status": "ok",
        "promotion": {
            "market": "KRW-XRP",
            "ready_for_review": True,
            "evaluation_status": "READY_FOR_REVIEW",
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
            "blocking_reasons": [],
            "reviewed_at": "2026-04-19T17:00:00+09:00",
        },
    }
    assert facade.build_history_response() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "reviewed_at": "2026-04-19T17:00:00+09:00",
                "evaluation_status": "READY_FOR_REVIEW",
                "ready_for_review": True,
                "live_enabled": True,
                "reason_code": None,
            }
        ],
    }
