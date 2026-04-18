from __future__ import annotations

from dataclasses import dataclass

from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.lifecycle import PromotionLifecycleService


@dataclass(frozen=True)
class PromotionReviewRequest:
    market: str
    demo_days: int
    total_trades: int
    profit_factor: float
    max_drawdown: float
    stoploss_failures: int
    approval_granted: bool
    approved_by: str
    activated_at: str


@dataclass(frozen=True)
class PromotionRunResult:
    evaluation: PromotionEvaluation
    approval_result: PromotionApprovalResult


class PromotionRunner:
    """Run promotion readiness and optional live approval as a single flow."""

    def __init__(self, *, lifecycle_service: PromotionLifecycleService) -> None:
        self._lifecycle_service = lifecycle_service

    def run(self, request: PromotionReviewRequest) -> PromotionRunResult:
        evaluation = self._lifecycle_service.evaluate_readiness(
            market=request.market,
            demo_days=request.demo_days,
            total_trades=request.total_trades,
            profit_factor=request.profit_factor,
            max_drawdown=request.max_drawdown,
            stoploss_failures=request.stoploss_failures,
        )
        approval_result = self._lifecycle_service.enable_live(
            market=request.market,
            evaluation=evaluation,
            approval_granted=request.approval_granted,
            approved_by=request.approved_by,
            activated_at=request.activated_at,
        )
        return PromotionRunResult(
            evaluation=evaluation,
            approval_result=approval_result,
        )
