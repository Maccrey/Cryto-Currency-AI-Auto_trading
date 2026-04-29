from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.history import PromotionHistoryStore
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService
from app.services.promotion.status import PromotionStatusStore
from app.services.promotion.evaluator import PromotionEvaluation


def test_save_review_updates_latest_and_history() -> None:
    service = PromotionStateService(
        status_store=PromotionStatusStore(),
        history_store=PromotionHistoryStore(),
    )
    result = PromotionRunResult(
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
    )

    snapshot = service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T13:00:00+09:00",
        result=result,
    )

    assert service.get_latest() == snapshot
    assert service.list_history() == [snapshot]


def test_payload_helpers_delegate_store_shapes() -> None:
    service = PromotionStateService()
    result = PromotionRunResult(
        evaluation=PromotionEvaluation(
            status="NOT_READY",
            approved=False,
            rejection_reasons=["LOW_SAMPLE_SIZE"],
        ),
        approval_result=PromotionApprovalResult(
            live_enabled=False,
            safe_mode_entry=False,
            reason_code="PROMOTION_NOT_READY",
        ),
    )
    snapshot = service.save_review(
        market="KRW-BTC",
        reviewed_at="2026-04-19T14:00:00+09:00",
        result=result,
    )

    assert service.to_payload(snapshot) == {
        "market": "KRW-BTC",
        "evaluation_status": "NOT_READY",
        "approved": False,
        "rejection_reasons": ["LOW_SAMPLE_SIZE"],
        "live_enabled": False,
        "safe_mode_entry": False,
        "reason_code": "PROMOTION_NOT_READY",
        "reviewed_at": "2026-04-19T14:00:00+09:00",
    }
    assert service.to_history_payload(service.list_history()) == [
        {
            "market": "KRW-BTC",
            "evaluation_status": "NOT_READY",
            "approved": False,
            "rejection_reasons": ["LOW_SAMPLE_SIZE"],
            "live_enabled": False,
            "safe_mode_entry": False,
            "reason_code": "PROMOTION_NOT_READY",
            "reviewed_at": "2026-04-19T14:00:00+09:00",
        }
    ]


def test_response_builders_return_empty_without_saved_review() -> None:
    service = PromotionStateService()

    assert service.is_ready_for_review() is False
    assert service.build_status_response() == {
        "status": "empty",
        "snapshot": None,
    }
    assert service.build_history_response() == {
        "status": "empty",
        "history": [],
    }
    assert service.build_state_overview() == {
        "status": "empty",
        "ready_for_review": False,
        "live_enabled": False,
        "reviewed_at": None,
        "blocking_reason_count": 0,
    }


def test_response_builders_return_review_and_status_payloads() -> None:
    service = PromotionStateService()
    result = PromotionRunResult(
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
    )

    service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T15:00:00+09:00",
        result=result,
    )

    assert service.is_ready_for_review() is True
    assert service.build_review_response(result) == {
        "status": "ok",
        "evaluation": {
            "status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
        },
        "approval_result": {
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
        },
    }
    assert service.build_status_response() == {
        "status": "ok",
        "snapshot": {
            "market": "KRW-XRP",
            "evaluation_status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
            "reviewed_at": "2026-04-19T15:00:00+09:00",
        },
    }
    assert service.build_history_response() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "evaluation_status": "READY_FOR_REVIEW",
                "approved": False,
                "rejection_reasons": [],
                "live_enabled": True,
                "safe_mode_entry": True,
                "reason_code": None,
                "reviewed_at": "2026-04-19T15:00:00+09:00",
            }
        ],
    }
    assert service.build_state_overview() == {
        "status": "READY_FOR_REVIEW",
        "ready_for_review": True,
        "live_enabled": True,
        "reviewed_at": "2026-04-19T15:00:00+09:00",
        "blocking_reason_count": 0,
    }
