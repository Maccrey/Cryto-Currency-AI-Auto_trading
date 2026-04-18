from __future__ import annotations

from app.services.promotion.approval import PromotionApprovalFlow, PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation


def test_promotion_approval_flow_blocks_live_enable_before_approval() -> None:
    flow = PromotionApprovalFlow()
    evaluation = PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )

    result = flow.enable_live(evaluation=evaluation, approval_granted=False)

    assert result == PromotionApprovalResult(
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="MANUAL_APPROVAL_REQUIRED",
    )


def test_promotion_approval_flow_enables_live_in_safe_mode_after_approval() -> None:
    flow = PromotionApprovalFlow()
    evaluation = PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )

    result = flow.enable_live(evaluation=evaluation, approval_granted=True)

    assert result == PromotionApprovalResult(
        live_enabled=True,
        safe_mode_entry=True,
        reason_code=None,
    )


def test_promotion_approval_flow_blocks_when_not_ready() -> None:
    flow = PromotionApprovalFlow()
    evaluation = PromotionEvaluation(
        status="NOT_READY",
        approved=False,
        rejection_reasons=["PROFIT_FACTOR_BELOW_THRESHOLD"],
    )

    result = flow.enable_live(evaluation=evaluation, approval_granted=True)

    assert result == PromotionApprovalResult(
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="PROMOTION_NOT_READY",
    )

