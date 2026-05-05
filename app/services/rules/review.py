from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.replay.harness import ReplayHarness
from app.services.replay.loader import ReplayFixtureLoader


@dataclass(frozen=True)
class RuleReviewConfig:
    enabled: bool
    window_days: int
    min_trades: int
    min_stoplosses: int
    max_params_per_run: int
    apply_target: str
    require_manual_approval: bool


class RuleReviewService:
    """Build rule improvement reviews and guard proposal promotion steps."""

    def __init__(
        self,
        *,
        market: str,
        trading_mode: str,
        learning_log_dir: Path,
        config: RuleReviewConfig,
    ) -> None:
        self._market = market
        self._trading_mode = trading_mode
        self._learning_log_dir = learning_log_dir
        self._config = config
        self._state_path = self._learning_log_dir / "rule-review-state.json"
        state = self._load_state()
        self._reviews: dict[str, dict[str, Any]] = state["reviews"]
        self._proposals: dict[str, dict[str, Any]] = state["proposals"]

    def review(self) -> dict[str, object]:
        metrics = self._collect_metrics()
        review = {
            "id": str(uuid4()),
            "market": self._market,
            "mode": self._trading_mode,
            "enabled": self._config.enabled,
            "analysis_window_days": self._config.window_days,
            "trade_count": metrics["trade_count"],
            "stop_loss_count": metrics["stop_loss_count"],
            "major_loss_causes": metrics["major_loss_causes"],
            "approval_required": self._config.require_manual_approval,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._reviews[str(review["id"])] = review
        self._save_state()
        return {"review": review}

    def create_proposal(
        self,
        *,
        review_id: str | None = None,
        proposed_changes: list[dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        review = self._reviews.get(str(review_id)) if review_id else None
        if review is None:
            review = self.review()["review"]  # type: ignore[assignment]

        rejection_reasons: list[str] = []
        if not self._config.enabled:
            rejection_reasons.append("rule_review_disabled")
        if int(review["trade_count"]) < self._config.min_trades:
            rejection_reasons.append("insufficient_trade_sample")
        if int(review["stop_loss_count"]) < self._config.min_stoplosses:
            rejection_reasons.append("insufficient_stoploss_sample")

        changes = [] if rejection_reasons else proposed_changes or self._default_proposed_changes()
        if len(changes) > self._config.max_params_per_run:
            rejection_reasons.append("too_many_parameter_changes")
            changes = changes[: self._config.max_params_per_run]

        proposal = {
            "id": str(uuid4()),
            "review_id": review["id"],
            "status": "blocked" if rejection_reasons else "proposed",
            "apply_target": self._config.apply_target,
            "analysis_window_days": review["analysis_window_days"],
            "trade_count": review["trade_count"],
            "stop_loss_count": review["stop_loss_count"],
            "major_loss_causes": review["major_loss_causes"],
            "codex_suggested_changes": changes,
            "replay_result": None,
            "demo_applied": False,
            "live_approved": False,
            "approval_required": self._config.require_manual_approval,
            "rejection_reasons": rejection_reasons,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._proposals[str(proposal["id"])] = proposal
        self._save_state()
        return {"proposal": proposal}

    def get_proposal(self, proposal_id: str) -> dict[str, object]:
        return {"proposal": self._proposals[proposal_id]}

    def list_proposals(self, *, limit: int = 20) -> dict[str, object]:
        proposals = sorted(
            self._proposals.values(),
            key=lambda proposal: str(proposal.get("created_at", "")),
            reverse=True,
        )
        limited = proposals[: max(limit, 0)]
        return {
            "count": len(limited),
            "total_count": len(proposals),
            "latest_proposal": limited[0] if limited else None,
            "proposals": limited,
        }

    def verify_replay(self, proposal_id: str, *, fixture_path: Path) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        ticks = ReplayFixtureLoader().load(fixture_path)
        results = ReplayHarness().run(ticks)
        blocked_count = sum(1 for result in results if result.blocked)
        signal_count = len(results)
        passed = signal_count > 0 and blocked_count < signal_count
        proposal["replay_result"] = {
            "status": "passed" if passed else "failed",
            "fixture_path": str(fixture_path),
            "signal_count": signal_count,
            "blocked_count": blocked_count,
            "max_signal_score": max((result.signal_score for result in results), default=0.0),
            "verified_at": datetime.now(UTC).isoformat(),
        }
        if not passed:
            reasons = set(proposal["rejection_reasons"])
            reasons.add("replay_failed")
            proposal["rejection_reasons"] = sorted(reasons)
            proposal["status"] = "blocked"
        else:
            reasons = set(proposal["rejection_reasons"])
            reasons.discard("replay_required")
            reasons.discard("replay_failed")
            proposal["rejection_reasons"] = sorted(reasons)
        self._save_state()
        return {"proposal": proposal}

    def apply_demo(self, proposal_id: str) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        reasons = set(proposal["rejection_reasons"])
        if proposal["replay_result"] is None:
            reasons.add("replay_required")
        elif proposal["replay_result"].get("status") != "passed":
            reasons.add("replay_failed")
        if proposal["status"] == "blocked":
            reasons.add("proposal_blocked")
        proposal["rejection_reasons"] = sorted(reasons)
        proposal["demo_applied"] = not proposal["rejection_reasons"]
        if proposal["demo_applied"]:
            proposal["status"] = "demo_applied"
            proposal["demo_applied_at"] = datetime.now(UTC).isoformat()
        self._save_state()
        return {"proposal": proposal}

    def approve_live(self, proposal_id: str, *, approved_by: str) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        reasons = set(proposal["rejection_reasons"])
        if not proposal["demo_applied"]:
            reasons.add("demo_apply_required")
        if self._config.require_manual_approval and not approved_by.strip():
            reasons.add("manual_approval_required")
        proposal["rejection_reasons"] = sorted(reasons)
        proposal["live_approved"] = not proposal["rejection_reasons"]
        if proposal["live_approved"]:
            proposal["status"] = "live_approved"
            proposal["approved_by"] = approved_by
            proposal["approved_at"] = datetime.now(UTC).isoformat()
        self._save_state()
        return {"proposal": proposal}

    def _load_state(self) -> dict[str, dict[str, dict[str, Any]]]:
        empty: dict[str, dict[str, dict[str, Any]]] = {
            "reviews": {},
            "proposals": {},
        }
        if not self._state_path.exists():
            return empty
        try:
            raw_state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return empty
        if not isinstance(raw_state, dict):
            return empty
        reviews = raw_state.get("reviews", {})
        proposals = raw_state.get("proposals", {})
        return {
            "reviews": reviews if isinstance(reviews, dict) else {},
            "proposals": proposals if isinstance(proposals, dict) else {},
        }

    def _save_state(self) -> None:
        self._learning_log_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "reviews": self._reviews,
            "proposals": self._proposals,
        }
        self._state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _collect_metrics(self) -> dict[str, object]:
        trade_count = 0
        stop_loss_count = 0
        cause_counts: dict[str, int] = {}
        log_path = self._learning_log_dir / "learning.jsonl"
        if log_path.exists():
            for raw_line in log_path.read_text(encoding="utf-8").splitlines():
                if not raw_line.strip():
                    continue
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                event_name = str(row.get("event_name", ""))
                payload = row.get("payload") or {}
                if event_name in {"fill_result", "position_closed"}:
                    trade_count += 1
                if event_name == "stop_loss_triggered" or payload.get("is_stop_loss"):
                    stop_loss_count += 1
                    reason = str(payload.get("reason_code") or payload.get("stop_loss_reason") or "unknown")
                    cause_counts[reason] = cause_counts.get(reason, 0) + 1
        causes = [
            {"reason": reason, "count": count}
            for reason, count in sorted(cause_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        return {
            "trade_count": trade_count,
            "stop_loss_count": stop_loss_count,
            "major_loss_causes": causes[:5],
        }

    @staticmethod
    def _default_proposed_changes() -> list[dict[str, object]]:
        return [
            {
                "file": "STRATEGY_SPEC.md",
                "parameter": "rule_review_candidate",
                "current_value": None,
                "proposed_value": "pending_codex_patch",
                "reason": "학습 로그 분석 후 Codex가 제한된 변경안을 작성해야 합니다.",
            },
        ]
