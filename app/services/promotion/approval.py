from __future__ import annotations

from dataclasses import dataclass

from app.services.promotion.evaluator import PromotionEvaluation


@dataclass(frozen=True)
class PromotionApprovalResult:
    live_enabled: bool
    safe_mode_entry: bool
    reason_code: str | None


class PromotionApprovalFlow:
    """Gate live activation behind readiness and explicit approval."""

    def enable_live(
        self,
        *,
        evaluation: PromotionEvaluation,
        approval_granted: bool,
    ) -> PromotionApprovalResult:
        if evaluation.status != "READY_FOR_REVIEW":
            return PromotionApprovalResult(
                live_enabled=False,
                safe_mode_entry=False,
                reason_code="PROMOTION_NOT_READY",
            )

        if not approval_granted:
            return PromotionApprovalResult(
                live_enabled=False,
                safe_mode_entry=False,
                reason_code="MANUAL_APPROVAL_REQUIRED",
            )

        return PromotionApprovalResult(
            live_enabled=True,
            safe_mode_entry=True,
            reason_code=None,
        )
