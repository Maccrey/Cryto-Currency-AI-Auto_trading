from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rules.review import RuleReviewService


class RuleProposalPayload(BaseModel):
    review_id: str | None = None


class RuleLiveApprovalPayload(BaseModel):
    approved_by: str = ""


def build_rules_router(*, rule_review_service: RuleReviewService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/rules")

    @router.post("/review")
    def review_rules() -> dict[str, object]:
        return rule_review_service.review()

    @router.post("/proposals")
    def create_rule_proposal(payload: RuleProposalPayload | None = None) -> dict[str, object]:
        return rule_review_service.create_proposal(
            review_id=None if payload is None else payload.review_id,
        )

    @router.get("/proposals/{proposal_id}")
    def get_rule_proposal(proposal_id: str) -> dict[str, object]:
        return rule_review_service.get_proposal(proposal_id)

    @router.post("/proposals/{proposal_id}/apply-demo")
    def apply_rule_proposal_to_demo(proposal_id: str) -> dict[str, object]:
        return rule_review_service.apply_demo(proposal_id)

    @router.post("/proposals/{proposal_id}/approve-live")
    def approve_rule_proposal_for_live(
        proposal_id: str,
        payload: RuleLiveApprovalPayload | None = None,
    ) -> dict[str, object]:
        return rule_review_service.approve_live(
            proposal_id,
            approved_by="" if payload is None else payload.approved_by,
        )

    return router
