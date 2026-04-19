from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.learning.service import LearningEvent, LearningService
from app.services.promotion.runner import PromotionReviewRequest, PromotionRunner
from app.services.promotion.state import PromotionStateService


@dataclass(frozen=True)
class PromotionReviewCommand:
    market: str
    demo_days: int
    total_trades: int
    profit_factor: float
    max_drawdown: float
    stoploss_failures: int
    approval_granted: bool
    approved_by: str
    activated_at: str


class PromotionReviewService:
    """Run promotion review end-to-end and persist its side effects."""

    def __init__(
        self,
        *,
        promotion_runner: PromotionRunner,
        promotion_state_service: PromotionStateService,
        learning_service: LearningService,
        trading_mode: str,
    ) -> None:
        self._promotion_runner = promotion_runner
        self._promotion_state_service = promotion_state_service
        self._learning_service = learning_service
        self._trading_mode = trading_mode

    def review(self, command: PromotionReviewCommand) -> dict[str, object]:
        request = self.build_request(command)
        result = self._promotion_runner.run(request)
        self._promotion_state_service.save_review(
            market=command.market,
            reviewed_at=command.activated_at,
            result=result,
        )
        self._learning_service.record(
            self.build_learning_event(command, result),
        )
        return self._promotion_state_service.build_review_response(result)

    @staticmethod
    def build_request(command: PromotionReviewCommand) -> PromotionReviewRequest:
        return PromotionReviewRequest(
            market=command.market,
            demo_days=command.demo_days,
            total_trades=command.total_trades,
            profit_factor=command.profit_factor,
            max_drawdown=command.max_drawdown,
            stoploss_failures=command.stoploss_failures,
            approval_granted=command.approval_granted,
            approved_by=command.approved_by,
            activated_at=command.activated_at,
        )

    def build_learning_event(
        self,
        command: PromotionReviewCommand,
        result,
    ) -> LearningEvent:
        return LearningEvent(
            event_name="promotion_review_completed",
            market=command.market,
            mode=self._trading_mode,
            payload={
                "demo_days": command.demo_days,
                "total_trades": command.total_trades,
                "profit_factor": command.profit_factor,
                "max_drawdown": command.max_drawdown,
                "stoploss_failures": command.stoploss_failures,
                "approval_granted": command.approval_granted,
                "approved_by": command.approved_by,
                "activated_at": command.activated_at,
                "evaluation_status": result.evaluation.status,
                "approved": result.evaluation.approved,
                "rejection_reasons": result.evaluation.rejection_reasons,
                "live_enabled": result.approval_result.live_enabled,
                "safe_mode_entry": result.approval_result.safe_mode_entry,
                "reason_code": result.approval_result.reason_code,
            },
        )

    @staticmethod
    def build_command(payload: dict[str, Any]) -> PromotionReviewCommand:
        return PromotionReviewCommand(
            market=str(payload["market"]),
            demo_days=int(payload["demo_days"]),
            total_trades=int(payload["total_trades"]),
            profit_factor=float(payload["profit_factor"]),
            max_drawdown=float(payload["max_drawdown"]),
            stoploss_failures=int(payload["stoploss_failures"]),
            approval_granted=bool(payload["approval_granted"]),
            approved_by=str(payload["approved_by"]),
            activated_at=str(payload["activated_at"]),
        )
