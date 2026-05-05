from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rules.review import RuleReviewService


class RuleProposalPayload(BaseModel):
    review_id: str | None = None
    proposed_changes: list[dict[str, object]] | None = None


class RuleLiveApprovalPayload(BaseModel):
    approved_by: str = ""


class RuleReplayPayload(BaseModel):
    fixture_path: str = "fixtures/replay_ticks.json"


class RuleCommitHashPayload(BaseModel):
    commit_hash: str = ""


class RuleHistoryCorrectionPayload(BaseModel):
    reason: str = ""
    corrected_fields: dict[str, object] | None = None
    corrected_by: str = ""


class RuleRollbackPayload(BaseModel):
    reason: str = ""
    target: str = "demo"
    rolled_back_by: str = ""


def build_rules_router(*, rule_review_service: RuleReviewService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/rules")

    @router.post("/review")
    def review_rules() -> dict[str, object]:
        return rule_review_service.review()

    @router.post("/proposals")
    def create_rule_proposal(payload: RuleProposalPayload | None = None) -> dict[str, object]:
        return rule_review_service.create_proposal(
            review_id=None if payload is None else payload.review_id,
            proposed_changes=None if payload is None else payload.proposed_changes,
        )

    @router.get("/proposals")
    def list_rule_proposals(limit: int = 20) -> dict[str, object]:
        return rule_review_service.list_proposals(limit=limit)

    @router.get("/history")
    def list_rule_change_history(limit: int = 50) -> dict[str, object]:
        return rule_review_service.list_history(limit=limit)

    @router.get("/proposals/{proposal_id}")
    def get_rule_proposal(proposal_id: str) -> dict[str, object]:
        return rule_review_service.get_proposal(proposal_id)

    @router.post("/proposals/{proposal_id}/apply-demo")
    def apply_rule_proposal_to_demo(proposal_id: str) -> dict[str, object]:
        return rule_review_service.apply_demo(proposal_id)

    @router.post("/proposals/{proposal_id}/replay")
    def replay_rule_proposal(
        proposal_id: str,
        payload: RuleReplayPayload | None = None,
    ) -> dict[str, object]:
        fixture_path = "fixtures/replay_ticks.json" if payload is None else payload.fixture_path
        return rule_review_service.verify_replay(
            proposal_id,
            fixture_path=Path(fixture_path),
        )

    @router.post("/proposals/{proposal_id}/commit-hash")
    def attach_rule_proposal_commit_hash(
        proposal_id: str,
        payload: RuleCommitHashPayload,
    ) -> dict[str, object]:
        return rule_review_service.attach_commit_hash(
            proposal_id,
            commit_hash=payload.commit_hash,
        )

    @router.post("/proposals/{proposal_id}/history-corrections")
    def append_rule_change_history_correction(
        proposal_id: str,
        payload: RuleHistoryCorrectionPayload,
    ) -> dict[str, object]:
        return rule_review_service.append_history_correction(
            proposal_id,
            reason=payload.reason,
            corrected_fields=payload.corrected_fields,
            corrected_by=payload.corrected_by,
        )

    @router.post("/proposals/{proposal_id}/rollback")
    def rollback_rule_proposal(
        proposal_id: str,
        payload: RuleRollbackPayload,
    ) -> dict[str, object]:
        return rule_review_service.rollback_proposal(
            proposal_id,
            reason=payload.reason,
            target=payload.target,
            rolled_back_by=payload.rolled_back_by,
        )

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
