from app.services.learning.service import LearningEvent
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.review import PromotionReviewCommand, PromotionReviewService
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService


class PromotionRunnerStub:
    def __init__(self, result: PromotionRunResult) -> None:
        self.result = result
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return self.result


class LearningServiceStub:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)


def test_review_runs_runner_and_persists_side_effects() -> None:
    runner = PromotionRunnerStub(
        PromotionRunResult(
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
    learning_service = LearningServiceStub()
    state_service = PromotionStateService()
    service = PromotionReviewService(
        promotion_runner=runner,
        promotion_state_service=state_service,
        learning_service=learning_service,
        trading_mode="demo",
    )
    command = PromotionReviewCommand(
        market="KRW-XRP",
        demo_days=16,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
        stoploss_failures=0,
        approval_granted=True,
        approved_by="manual_review",
        activated_at="2026-04-19T16:00:00+09:00",
    )

    response = service.review(command)

    assert len(runner.requests) == 1
    assert runner.requests[0].market == "KRW-XRP"
    assert state_service.get_latest() is not None
    assert len(state_service.list_history()) == 1
    assert len(learning_service.events) == 1
    assert learning_service.events[0].event_name == "promotion_review_completed"
    assert learning_service.events[0].mode == "demo"
    assert response == {
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


def test_build_command_normalizes_payload_types() -> None:
    command = PromotionReviewService.build_command(
        {
            "market": "KRW-BTC",
            "demo_days": "14",
            "total_trades": "100",
            "profit_factor": "1.2",
            "max_drawdown": "0.08",
            "stoploss_failures": "0",
            "approval_granted": True,
            "approved_by": "ops",
            "activated_at": "2026-04-19T16:10:00+09:00",
        },
    )

    assert command == PromotionReviewCommand(
        market="KRW-BTC",
        demo_days=14,
        total_trades=100,
        profit_factor=1.2,
        max_drawdown=0.08,
        stoploss_failures=0,
        approval_granted=True,
        approved_by="ops",
        activated_at="2026-04-19T16:10:00+09:00",
    )
