from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.learning.service import LearningEvent, LearningService
from app.services.rules.review import RuleReviewService


class RuleProposalPayload(BaseModel):
    review_id: str | None = None
    proposed_changes: list[dict[str, object]] | None = None
    auto_apply: bool = True
    fixture_path: str = "fixtures/replay_ticks.json"


class RuleLiveApprovalPayload(BaseModel):
    approved_by: str = ""


class RuleReplayPayload(BaseModel):
    fixture_path: str = "fixtures/replay_ticks.json"


class RuleAutoImprovePayload(BaseModel):
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


def build_rules_router(
    *,
    rule_review_service: RuleReviewService,
    learning_service: LearningService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/rules")

    @router.post("/review")
    def review_rules() -> dict[str, object]:
        return rule_review_service.review()

    @router.post("/proposals")
    def create_rule_proposal(payload: RuleProposalPayload | None = None) -> dict[str, object]:
        result = rule_review_service.create_proposal(
            review_id=None if payload is None else payload.review_id,
            proposed_changes=None if payload is None else payload.proposed_changes,
        )
        auto_apply = True if payload is None else payload.auto_apply
        if not auto_apply:
            return result

        proposal = result["proposal"]
        auto_apply_result = {
            "enabled": True,
            "fixture_path": "fixtures/replay_ticks.json" if payload is None else payload.fixture_path,
            "replay_status": "skipped",
            "demo_applied": bool(proposal.get("demo_applied")),
        }
        if proposal.get("status") != "blocked":
            replay_result = rule_review_service.verify_replay(
                str(proposal["id"]),
                fixture_path=Path(str(auto_apply_result["fixture_path"])),
            )
            proposal = replay_result["proposal"]
            auto_apply_result["replay_status"] = str((proposal.get("replay_result") or {}).get("status", "unknown"))
            demo_result = rule_review_service.apply_demo(str(proposal["id"]))
            proposal = demo_result["proposal"]
            auto_apply_result["demo_applied"] = bool(proposal.get("demo_applied"))
        else:
            auto_apply_result["replay_status"] = "blocked"
        return {"proposal": proposal, "auto_apply": auto_apply_result}

    @router.get("/proposals")
    def list_rule_proposals(limit: int = 20) -> dict[str, object]:
        return rule_review_service.list_proposals(limit=limit)

    @router.get("/history")
    def list_rule_change_history(limit: int = 50) -> dict[str, object]:
        return rule_review_service.list_history(limit=limit)

    @router.post("/auto-improve")
    def auto_improve_rules(payload: RuleAutoImprovePayload | None = None) -> dict[str, object]:
        fixture_path = "fixtures/replay_ticks.json" if payload is None else payload.fixture_path
        result = rule_review_service.auto_improve(fixture_path=Path(fixture_path))
        if learning_service is not None:
            reset_learning_completion = result.get("status") == "completed"
            if reset_learning_completion:
                learning_service.record(
                    LearningEvent(
                        event_name="auto_rule_update",
                        market=str(getattr(rule_review_service, "_market", "unknown")),
                        mode=str(getattr(rule_review_service, "_trading_mode", "unknown")),
                        payload={
                            "status": result.get("status", "unknown"),
                            "reset_learning_completion": True,
                            "trigger_reason": result.get("trigger_reason", "manual"),
                            "rule_changed": bool((result.get("proposal") or {}).get("demo_applied")),
                        },
                    ),
                )
            result["reset_learning_completion"] = reset_learning_completion
        return result

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
