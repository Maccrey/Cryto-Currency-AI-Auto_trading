from __future__ import annotations

from app.integrations.telegram.lifecycle_notification_dispatcher import (
    LifecycleNotificationDispatcher,
)
from app.services.promotion.approval import PromotionApprovalFlow, PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation, PromotionEvaluator


class PromotionLifecycleService:
    """Coordinate promotion evaluation, approval, and operational notifications."""

    def __init__(
        self,
        *,
        evaluator: PromotionEvaluator,
        approval_flow: PromotionApprovalFlow,
        notification_dispatcher: LifecycleNotificationDispatcher | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._approval_flow = approval_flow
        self._notification_dispatcher = notification_dispatcher

    def evaluate_readiness(
        self,
        *,
        market: str,
        demo_days: int,
        total_trades: int,
        profit_factor: float,
        max_drawdown: float,
        stoploss_failures: int,
    ) -> PromotionEvaluation:
        evaluation = self._evaluator.evaluate(
            demo_days=demo_days,
            total_trades=total_trades,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            stoploss_failures=stoploss_failures,
        )
        if (
            evaluation.status == "READY_FOR_REVIEW"
            and self._notification_dispatcher is not None
        ):
            self._notification_dispatcher.dispatch_promotion_ready(
                market=market,
                demo_days=demo_days,
                total_trades=total_trades,
                profit_factor=profit_factor,
                max_drawdown=max_drawdown,
            )
        return evaluation

    def enable_live(
        self,
        *,
        market: str,
        evaluation: PromotionEvaluation,
        approval_granted: bool,
        approved_by: str,
        activated_at: str,
    ) -> PromotionApprovalResult:
        result = self._approval_flow.enable_live(
            evaluation=evaluation,
            approval_granted=approval_granted,
        )
        if result.live_enabled and self._notification_dispatcher is not None:
            self._notification_dispatcher.dispatch_live_enabled(
                market=market,
                approved_by=approved_by,
                activated_at=activated_at,
            )
        return result
