from __future__ import annotations

import json
from collections import Counter
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
    auto_update_enabled: bool = False
    auto_update_min_learning_completion_rate: float = 1.0
    auto_update_win_rate_skip_threshold: float = 0.80


class RuleReviewService:
    """Build rule improvement reviews and guard proposal promotion steps."""

    LOCKED_PARAMETER_PREFIXES = ("STOP_LOSS_",)
    LOCKED_PARAMETER_NAMES = {
        "stop_loss_pct",
        "stop_loss_price",
        "fixed_stop_loss_pct",
    }

    def __init__(
        self,
        *,
        market: str,
        trade_coin: str | None = None,
        trading_mode: str,
        learning_log_dir: Path,
        config: RuleReviewConfig,
    ) -> None:
        self._market = market
        self._trade_coin = (trade_coin or market.split("-")[-1]).upper()
        self._trading_mode = trading_mode
        self._learning_log_dir = learning_log_dir
        self._config = config
        self._state_path = self._learning_log_dir / "rule-review-state.json"
        self._history_path = self._learning_log_dir / "rule-change-history.jsonl"
        state = self._load_state()
        self._reviews: dict[str, dict[str, Any]] = state["reviews"]
        self._proposals: dict[str, dict[str, Any]] = state["proposals"]

    def review(self) -> dict[str, object]:
        metrics = self._collect_metrics()
        review = {
            "id": str(uuid4()),
            "market": self._market,
            "trade_coin": self._trade_coin,
            "mode": self._trading_mode,
            "learning_log_dir": str(self._learning_log_dir),
            "enabled": self._config.enabled,
            "analysis_window_days": self._config.window_days,
            "trade_count": metrics["trade_count"],
            "stop_loss_count": metrics["stop_loss_count"],
            "major_loss_causes": metrics["major_loss_causes"],
            "blocked_reason_summary": metrics["blocked_reason_summary"],
            "sizing_blocked_reason_summary": metrics["sizing_blocked_reason_summary"],
            "no_trade_blocked_count": metrics["no_trade_blocked_count"],
            "learning_completion_rate": metrics["learning_completion_rate"],
            "win_rate": metrics["win_rate"],
            "external_context_summary": metrics["external_context_summary"],
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
        no_trade_mitigation = self._is_no_trade_mitigation_candidate(review)
        if not self._config.enabled:
            rejection_reasons.append("rule_review_disabled")
        if int(review["trade_count"]) < self._config.min_trades and not no_trade_mitigation:
            rejection_reasons.append("insufficient_trade_sample")
        if int(review["stop_loss_count"]) < self._config.min_stoplosses and not no_trade_mitigation:
            rejection_reasons.append("insufficient_stoploss_sample")

        changes = [] if rejection_reasons else proposed_changes or self._default_proposed_changes(review)
        locked_changes = self._locked_changes(changes)
        if locked_changes:
            rejection_reasons.append("fixed_stop_loss_locked")
            changes = self._without_locked_changes(changes)
        if len(changes) > self._config.max_params_per_run:
            rejection_reasons.append("too_many_parameter_changes")
            changes = changes[: self._config.max_params_per_run]
        history_warnings = self._history_warnings_for_changes(changes)

        proposal = {
            "id": str(uuid4()),
            "review_id": review["id"],
            "market": self._market,
            "trade_coin": self._trade_coin,
            "learning_log_dir": str(self._learning_log_dir),
            "status": "blocked" if rejection_reasons else "proposed",
            "apply_target": self._config.apply_target,
            "analysis_window_days": review["analysis_window_days"],
            "trade_count": review["trade_count"],
            "stop_loss_count": review["stop_loss_count"],
            "major_loss_causes": review["major_loss_causes"],
            "blocked_reason_summary": review.get("blocked_reason_summary", []),
            "sizing_blocked_reason_summary": review.get("sizing_blocked_reason_summary", []),
            "no_trade_blocked_count": review.get("no_trade_blocked_count", 0),
            "learning_completion_rate": review.get("learning_completion_rate", 0.0),
            "win_rate": review.get("win_rate", 0.0),
            "external_context_summary": review.get("external_context_summary", self._empty_external_context_summary()),
            "codex_suggested_changes": changes,
            "locked_parameters": self._changed_parameters(locked_changes),
            "history_warnings": history_warnings,
            "replay_result": None,
            "demo_applied": False,
            "live_approved": False,
            "approval_required": self._config.require_manual_approval,
            "rejection_reasons": rejection_reasons,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._proposals[str(proposal["id"])] = proposal
        self._save_state()
        self._append_history_event(
            event_type="proposal_created",
            proposal=proposal,
            review=review,
            approval_status="pending",
        )
        return {"proposal": proposal}

    def auto_improve(self, *, fixture_path: Path) -> dict[str, object]:
        steps: list[dict[str, object]] = []

        review_response = self.review()
        review = review_response["review"]
        auto_gate_reasons = self._auto_update_gate_reasons(review)
        steps.append(
            {
                "name": "Codex CLI 룰 개선 하네스 시작",
                "status": "blocked" if auto_gate_reasons else "completed",
                "message": (
                    "자동 룰 업데이트 조건을 충족하지 못했습니다: " + ", ".join(auto_gate_reasons)
                    if auto_gate_reasons
                    else "학습 로그 기반 자동 룰 개선 파이프라인을 시작했습니다."
                ),
            },
        )
        steps.append(
            {
                "name": "룰 개선 분석",
                "status": "completed",
                "message": (
                    f"최근 {review['analysis_window_days']}일 로그에서 거래 {review['trade_count']}건, "
                    f"손절 {review['stop_loss_count']}건을 집계했습니다."
                ),
                "payload": review,
            },
        )

        proposal_response = self.create_proposal(review_id=str(review["id"]))
        proposal = proposal_response["proposal"]
        if auto_gate_reasons:
            proposal["rejection_reasons"] = sorted(set(proposal.get("rejection_reasons", [])) | set(auto_gate_reasons))
            proposal["status"] = "blocked"
            self._proposals[str(proposal["id"])] = proposal
            self._save_state()
        proposal_blocked = bool(proposal.get("rejection_reasons"))
        steps.append(
            {
                "name": "Codex 룰 변경안 생성",
                "status": "blocked" if proposal_blocked else "completed",
                "message": self._proposal_step_message(proposal),
                "payload": proposal,
            },
        )

        replay_response = self.verify_replay(str(proposal["id"]), fixture_path=fixture_path)
        proposal = replay_response["proposal"]
        replay_result = proposal.get("replay_result") or {}
        replay_passed = replay_result.get("status") == "passed"
        steps.append(
            {
                "name": "replay 검증",
                "status": "completed" if replay_passed else "blocked",
                "message": self._replay_step_message(replay_result),
                "payload": replay_result,
            },
        )

        demo_response = self.apply_demo(str(proposal["id"]))
        proposal = demo_response["proposal"]
        demo_applied = bool(proposal.get("demo_applied"))
        steps.append(
            {
                "name": "demo 적용",
                "status": "completed" if demo_applied else "blocked",
                "message": (
                    "replay 통과 변경안을 demo에 적용했습니다."
                    if demo_applied
                    else f"demo 적용이 보류되었습니다: {', '.join(proposal.get('rejection_reasons', [])) or '사유 없음'}"
                ),
                "payload": proposal,
            },
        )

        final_summary = self._automation_summary(proposal)
        return {
            "status": "blocked" if auto_gate_reasons else ("completed" if demo_applied else "needs_retry"),
            "codex_cli": {
                "mode": "local_harness",
                "command": "codex rule-improve --from-learning-log --replay --apply-demo",
            },
            "steps": steps,
            "review": review,
            "proposal": proposal,
            "final_summary": final_summary,
            "can_retry": not demo_applied,
        }

    def get_proposal(self, proposal_id: str) -> dict[str, object]:
        return {"proposal": self._with_proposal_metadata(self._proposals[proposal_id])}

    def list_proposals(self, *, limit: int = 20) -> dict[str, object]:
        proposals = sorted(
            self._proposals.values(),
            key=lambda proposal: str(proposal.get("created_at", "")),
            reverse=True,
        )
        limited = proposals[: max(limit, 0)]
        return {
            "market": self._market,
            "trade_coin": self._trade_coin,
            "learning_log_dir": str(self._learning_log_dir),
            "count": len(limited),
            "total_count": len(proposals),
            "latest_proposal": self._with_proposal_metadata(limited[0]) if limited else None,
            "proposals": [self._with_proposal_metadata(proposal) for proposal in limited],
        }

    def list_history(self, *, limit: int = 50) -> dict[str, object]:
        history = self._read_history()
        limited = history[-max(limit, 0) :] if limit >= 0 else history
        limited = list(reversed(limited))
        return {
            "market": self._market,
            "trade_coin": self._trade_coin,
            "learning_log_dir": str(self._learning_log_dir),
            "history_path": str(self._history_path),
            "count": len(limited),
            "total_count": len(history),
            "history": limited,
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
        self._append_history_event(
            event_type="replay_verified",
            proposal=proposal,
            approval_status=str(proposal["replay_result"].get("status", "unknown")),
        )
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
        self._append_history_event(
            event_type="demo_applied" if proposal["demo_applied"] else "demo_apply_rejected",
            proposal=proposal,
            approval_status="applied" if proposal["demo_applied"] else "rejected",
        )
        return {"proposal": proposal}

    def approve_live(self, proposal_id: str, *, approved_by: str) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        reasons = set(proposal["rejection_reasons"])
        if not proposal["demo_applied"]:
            reasons.add("demo_apply_required")
        if self._config.require_manual_approval and not approved_by.strip():
            reasons.add("manual_approval_required")
        if not self._proposal_has_history(proposal_id):
            reasons.add("rule_change_history_required")
        proposal["rejection_reasons"] = sorted(reasons)
        proposal["live_approved"] = not proposal["rejection_reasons"]
        if proposal["live_approved"]:
            proposal["status"] = "live_approved"
            proposal["approved_by"] = approved_by
            proposal["approved_at"] = datetime.now(UTC).isoformat()
        self._save_state()
        self._append_history_event(
            event_type="live_approved" if proposal["live_approved"] else "live_approval_rejected",
            proposal=proposal,
            approval_status="approved" if proposal["live_approved"] else "rejected",
            approved_by=approved_by,
        )
        return {"proposal": proposal}

    def attach_commit_hash(self, proposal_id: str, *, commit_hash: str) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        normalized_commit_hash = commit_hash.strip()
        if not normalized_commit_hash:
            reasons = set(proposal["rejection_reasons"])
            reasons.add("commit_hash_required")
            proposal["rejection_reasons"] = sorted(reasons)
            self._save_state()
            return {"proposal": proposal}

        proposal["commit_hash"] = normalized_commit_hash
        self._save_state()
        self._append_history_event(
            event_type="commit_linked",
            proposal=proposal,
            approval_status="linked",
            commit_hash=normalized_commit_hash,
        )
        return {"proposal": proposal}

    def append_history_correction(
        self,
        proposal_id: str,
        *,
        reason: str,
        corrected_fields: dict[str, Any] | None = None,
        corrected_by: str = "",
    ) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        normalized_reason = reason.strip()
        if not normalized_reason:
            return {
                "proposal": proposal,
                "correction": None,
                "rejection_reasons": ["correction_reason_required"],
            }

        correction = {
            "reason": normalized_reason,
            "corrected_fields": corrected_fields or {},
            "corrected_by": corrected_by.strip(),
        }
        self._append_history_event(
            event_type="correction",
            proposal=proposal,
            approval_status="corrected",
            approved_by=corrected_by,
            change_reason=normalized_reason,
            extra_fields={"correction_detail": correction},
        )
        return {"proposal": proposal, "correction": correction}

    def rollback_proposal(
        self,
        proposal_id: str,
        *,
        reason: str,
        target: str = "demo",
        rolled_back_by: str = "",
    ) -> dict[str, object]:
        proposal = self._proposals[proposal_id]
        normalized_reason = reason.strip()
        normalized_target = target.strip() or "demo"
        if not normalized_reason:
            reasons = set(proposal["rejection_reasons"])
            reasons.add("rollback_reason_required")
            proposal["rejection_reasons"] = sorted(reasons)
            self._save_state()
            return {"proposal": proposal, "rollback": None}

        proposal["status"] = "rolled_back"
        proposal["rolled_back"] = True
        proposal["rolled_back_at"] = datetime.now(UTC).isoformat()
        proposal["rolled_back_by"] = rolled_back_by.strip()
        proposal["rollback_target"] = normalized_target
        if normalized_target == "live":
            proposal["live_approved"] = False
        if normalized_target == "demo":
            proposal["demo_applied"] = False
        rollback = {
            "reason": normalized_reason,
            "target": normalized_target,
            "rolled_back_by": rolled_back_by.strip(),
        }
        self._save_state()
        self._append_history_event(
            event_type="rollback",
            proposal=proposal,
            approval_status="rolled_back",
            approved_by=rolled_back_by,
            change_reason=normalized_reason,
            extra_fields={"rollback_detail": rollback},
        )
        return {"proposal": proposal, "rollback": rollback}

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

    def _with_proposal_metadata(self, proposal: dict[str, Any]) -> dict[str, Any]:
        proposal.setdefault("market", self._market)
        proposal.setdefault("trade_coin", self._trade_coin)
        proposal.setdefault("learning_log_dir", str(self._learning_log_dir))
        return proposal

    def _append_history_event(
        self,
        *,
        event_type: str,
        proposal: dict[str, Any],
        review: dict[str, Any] | None = None,
        approval_status: str,
        approved_by: str = "",
        commit_hash: str | None = None,
        change_reason: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        self._learning_log_dir.mkdir(parents=True, exist_ok=True)
        changes = proposal.get("codex_suggested_changes") or []
        change_reasons = [
            str(change.get("reason"))
            for change in changes
            if isinstance(change, dict) and change.get("reason")
        ]
        history = {
            "history_id": str(uuid4()),
            "event_type": event_type,
            "review_id": proposal.get("review_id"),
            "proposal_id": proposal.get("id"),
            "market": proposal.get("market", self._market),
            "trade_coin": proposal.get("trade_coin", self._trade_coin),
            "trading_profile": self._learning_log_dir.name,
            "mode": self._trading_mode,
            "learning_log_dir": str(self._learning_log_dir),
            "analysis_window_days": proposal.get("analysis_window_days"),
            "trade_count": proposal.get("trade_count"),
            "stop_loss_count": proposal.get("stop_loss_count"),
            "major_loss_causes": proposal.get("major_loss_causes", []),
            "blocked_reason_summary": proposal.get("rejection_reasons", []),
            "external_context_summary": proposal.get(
                "external_context_summary",
                self._empty_external_context_summary(),
            ),
            "previous_rule_snapshot": self._previous_rule_snapshot(changes),
            "proposed_rule_snapshot": self._proposed_rule_snapshot(changes),
            "changed_parameters": self._changed_parameters(changes),
            "change_reason": change_reason
            or "; ".join(change_reasons)
            or "학습 로그 기반 Codex 룰 개선 파이프라인 이벤트",
            "expected_effect": self._expected_effect(changes),
            "known_risks": self._known_risks(changes),
            "replay_result": proposal.get("replay_result"),
            "demo_result": {
                "demo_applied": proposal.get("demo_applied", False),
                "demo_applied_at": proposal.get("demo_applied_at"),
            },
            "approval_status": approval_status,
            "approved_by": approved_by or proposal.get("approved_by", ""),
            "applied_target": proposal.get("apply_target", self._config.apply_target),
            "created_at": datetime.now(UTC).isoformat(),
            "commit_hash": commit_hash or proposal.get("commit_hash", ""),
        }
        if extra_fields:
            history.update(extra_fields)
        if review is not None:
            history["review_created_at"] = review.get("created_at")
        with self._history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(history, ensure_ascii=True, sort_keys=True) + "\n")

    def _read_history(self) -> list[dict[str, Any]]:
        if not self._history_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self._history_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _proposal_has_history(self, proposal_id: str) -> bool:
        return any(str(row.get("proposal_id")) == str(proposal_id) for row in self._read_history())

    def _history_warnings_for_changes(self, changes: Any) -> list[dict[str, object]]:
        parameters = self._changed_parameters(changes)
        if not parameters:
            return []
        failed_events = {
            "replay_verified",
            "demo_apply_rejected",
            "live_approval_rejected",
            "rollback",
            "correction",
        }
        warnings: list[dict[str, object]] = []
        history = list(reversed(self._read_history()))
        for parameter in parameters:
            previous = next(
                (
                    row
                    for row in history
                    if parameter in [str(item) for item in row.get("changed_parameters", [])]
                    and (
                        str(row.get("event_type")) in failed_events
                        or str(row.get("approval_status")) in {"failed", "rejected", "rolled_back"}
                    )
                ),
                None,
            )
            if previous is None:
                continue
            warnings.append(
                {
                    "parameter": parameter,
                    "previous_proposal_id": previous.get("proposal_id", ""),
                    "previous_event_type": previous.get("event_type", ""),
                    "previous_approval_status": previous.get("approval_status", ""),
                    "previous_blocked_reasons": previous.get("blocked_reason_summary", []),
                    "message": f"{parameter} 파라미터는 과거 실패/거절 이력이 있습니다.",
                },
            )
        return warnings

    @staticmethod
    def _proposal_step_message(proposal: dict[str, Any]) -> str:
        changes = proposal.get("codex_suggested_changes") or []
        if proposal.get("rejection_reasons"):
            return f"변경안 생성이 보류되었습니다: {', '.join(proposal.get('rejection_reasons', []))}"
        if not changes:
            return "변경할 파라미터가 없습니다."
        parameters = ", ".join(str(change.get("parameter")) for change in changes if isinstance(change, dict))
        return f"Codex가 변경 후보 {len(changes)}개를 생성했습니다: {parameters}"

    @staticmethod
    def _replay_step_message(replay_result: dict[str, Any]) -> str:
        if not replay_result:
            return "replay 결과가 없습니다."
        return (
            f"{replay_result.get('status', 'unknown')} / "
            f"신호 {replay_result.get('signal_count', 0)}건, "
            f"차단 {replay_result.get('blocked_count', 0)}건, "
            f"최대 신호점수 {replay_result.get('max_signal_score', 0.0)}"
        )

    @staticmethod
    def _automation_summary(proposal: dict[str, Any]) -> dict[str, object]:
        changes = proposal.get("codex_suggested_changes") or []
        changed_parameters = [
            str(change.get("parameter"))
            for change in changes
            if isinstance(change, dict) and change.get("parameter")
        ]
        change_reasons = [
            str(change.get("reason"))
            for change in changes
            if isinstance(change, dict) and change.get("reason")
        ]
        return {
            "changed_parameters": changed_parameters,
            "change_reason": "; ".join(change_reasons) or "표본 부족 또는 차단 조건으로 실제 룰 변경 없음",
            "demo_applied": bool(proposal.get("demo_applied")),
            "live_requires_approval": bool(proposal.get("approval_required", True)),
            "rejection_reasons": proposal.get("rejection_reasons", []),
            "history_warnings": proposal.get("history_warnings", []),
            "replay_result": proposal.get("replay_result"),
        }

    def _collect_metrics(self) -> dict[str, object]:
        trade_count = 0
        stop_loss_count = 0
        cause_counts: dict[str, int] = {}
        blocked_reasons: Counter[str] = Counter()
        sizing_blocked_reasons: Counter[str] = Counter()
        context_samples: list[dict[str, Any]] = []
        completion_rates: list[float] = []
        closed_trade_pnls: list[float] = []
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
                if not isinstance(payload, dict):
                    payload = {}
                if event_name in {"fill_result", "position_closed"}:
                    trade_count += 1
                    if payload.get("side") == "sell" or event_name == "position_closed":
                        try:
                            closed_trade_pnls.append(float(payload.get("pnl", payload.get("realized_pnl", 0.0))))
                        except (TypeError, ValueError):
                            pass
                if event_name == "stop_loss_triggered" or payload.get("is_stop_loss"):
                    stop_loss_count += 1
                    reason = str(payload.get("reason_code") or payload.get("stop_loss_reason") or "unknown")
                    cause_counts[reason] = cause_counts.get(reason, 0) + 1
                if event_name == "auto_trade_cycle":
                    try:
                        completion_rates.append(float(payload.get("learning_completion_rate", 0.0)))
                    except (TypeError, ValueError):
                        pass
                    if payload.get("reason") is not None:
                        blocked_reasons.update([str(payload.get("reason"))])
                    if payload.get("sizing_blocked_reason") is not None:
                        sizing_blocked_reasons.update([str(payload.get("sizing_blocked_reason"))])
                context = payload.get("external_context") if event_name == "auto_trade_cycle" else payload
                if event_name in {"auto_trade_cycle", "external_market_context_snapshot"} and isinstance(context, dict):
                    context_samples.append(context)
        causes = [
            {"reason": reason, "count": count}
            for reason, count in sorted(cause_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        no_trade_blocked_count = (
            blocked_reasons.get("AUTO_MIN_SIGNAL_LEVEL", 0)
            + blocked_reasons.get("FEE_ADJUSTED_EDGE_LIMIT", 0)
            + sizing_blocked_reasons.get("FEE_ADJUSTED_EDGE_LIMIT", 0)
        )
        return {
            "trade_count": trade_count,
            "stop_loss_count": stop_loss_count,
            "major_loss_causes": causes[:5],
            "blocked_reason_summary": [
                {"reason": reason, "count": count}
                for reason, count in sorted(blocked_reasons.items(), key=lambda item: item[1], reverse=True)
            ],
            "sizing_blocked_reason_summary": [
                {"reason": reason, "count": count}
                for reason, count in sorted(sizing_blocked_reasons.items(), key=lambda item: item[1], reverse=True)
            ],
            "no_trade_blocked_count": no_trade_blocked_count,
            "external_context_summary": self._external_context_summary(context_samples),
            "learning_completion_rate": round(max(completion_rates, default=0.0), 3),
            "win_rate": self._win_rate(closed_trade_pnls),
        }

    def _auto_update_gate_reasons(self, review: dict[str, Any]) -> list[str]:
        if not self._config.auto_update_enabled:
            return []
        reasons: list[str] = []
        if float(review.get("learning_completion_rate") or 0.0) < self._config.auto_update_min_learning_completion_rate:
            reasons.append("learning_completion_incomplete")
        if float(review.get("win_rate") or 0.0) >= self._config.auto_update_win_rate_skip_threshold:
            reasons.append("win_rate_above_auto_update_threshold")
        return reasons

    @staticmethod
    def _win_rate(pnls: list[float]) -> float:
        if not pnls:
            return 0.0
        return round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 3)

    @staticmethod
    def _previous_rule_snapshot(changes: Any) -> dict[str, object]:
        if not isinstance(changes, list):
            return {}
        return {
            str(change.get("parameter")): change.get("current_value")
            for change in changes
            if isinstance(change, dict) and change.get("parameter")
        }

    @staticmethod
    def _proposed_rule_snapshot(changes: Any) -> dict[str, object]:
        if not isinstance(changes, list):
            return {}
        return {
            str(change.get("parameter")): change.get("proposed_value")
            for change in changes
            if isinstance(change, dict) and change.get("parameter")
        }

    @staticmethod
    def _changed_parameters(changes: Any) -> list[str]:
        if not isinstance(changes, list):
            return []
        return [
            str(change.get("parameter"))
            for change in changes
            if isinstance(change, dict) and change.get("parameter")
        ]

    @classmethod
    def _locked_changes(cls, changes: Any) -> list[dict[str, Any]]:
        if not isinstance(changes, list):
            return []
        return [
            change
            for change in changes
            if isinstance(change, dict) and cls._is_locked_parameter(change.get("parameter"))
        ]

    @classmethod
    def _without_locked_changes(cls, changes: Any) -> list[dict[str, Any]]:
        if not isinstance(changes, list):
            return []
        return [
            change
            for change in changes
            if isinstance(change, dict) and not cls._is_locked_parameter(change.get("parameter"))
        ]

    @classmethod
    def _is_locked_parameter(cls, parameter: Any) -> bool:
        normalized = str(parameter or "").strip()
        lowered = normalized.lower()
        return (
            lowered in cls.LOCKED_PARAMETER_NAMES
            or any(normalized.upper().startswith(prefix) for prefix in cls.LOCKED_PARAMETER_PREFIXES)
        )

    @staticmethod
    def _expected_effect(changes: Any) -> str:
        if not isinstance(changes, list) or not changes:
            return "룰 변경 없음 또는 표본 부족으로 변경 효과 없음"
        return "학습 로그에서 확인된 손실/차단 원인을 줄이고 replay와 demo에서 개선 여부를 검증"

    @staticmethod
    def _known_risks(changes: Any) -> str:
        if not isinstance(changes, list) or not changes:
            return "변경 없음"
        return "표본 과최적화, 특정 장세 편향, 손절/진입 빈도 변화 가능성"

    @staticmethod
    def _external_context_summary(samples: list[dict[str, Any]]) -> dict[str, object]:
        if not samples:
            return RuleReviewService._empty_external_context_summary()
        onchain_counts: Counter[str] = Counter()
        onchain_exchange_counts: Counter[str] = Counter()
        etf_counts: Counter[str] = Counter()
        weights: list[float] = []
        etf_flows: list[float] = []
        etf_inflows: list[float] = []
        etf_outflows: list[float] = []
        for sample in samples:
            onchain = sample.get("onchain") or {}
            etf = sample.get("etf") or {}
            if isinstance(onchain, dict):
                onchain_counts.update([str(onchain.get("state") or "unknown")])
                onchain_exchange_counts.update([str(onchain.get("exchange_netflow_state") or "unknown")])
            if isinstance(etf, dict):
                etf_counts.update([str(etf.get("state") or "unknown")])
                RuleReviewService._append_float(etf_flows, etf.get("flow_usd"))
                RuleReviewService._append_float(etf_inflows, etf.get("inflow_usd"))
                RuleReviewService._append_float(etf_outflows, etf.get("outflow_usd"))
            try:
                weights.append(float(sample.get("learning_weight", 1.0)))
            except (TypeError, ValueError):
                pass
        return {
            "sample_count": len(samples),
            "onchain_state_counts": dict(onchain_counts),
            "onchain_exchange_netflow_counts": dict(onchain_exchange_counts),
            "etf_state_counts": dict(etf_counts),
            "avg_learning_weight": round(sum(weights) / len(weights), 3) if weights else 1.0,
            "etf_flow_usd_total": round(sum(etf_flows), 2),
            "etf_inflow_usd_total": round(sum(etf_inflows), 2),
            "etf_outflow_usd_total": round(sum(etf_outflows), 2),
        }

    @staticmethod
    def _empty_external_context_summary() -> dict[str, object]:
        return {
            "sample_count": 0,
            "onchain_state_counts": {},
            "onchain_exchange_netflow_counts": {},
            "etf_state_counts": {},
            "avg_learning_weight": 1.0,
            "etf_flow_usd_total": 0.0,
            "etf_inflow_usd_total": 0.0,
            "etf_outflow_usd_total": 0.0,
        }

    @staticmethod
    def _append_float(values: list[float], value: Any) -> None:
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            pass

    def _is_no_trade_mitigation_candidate(self, review: dict[str, Any]) -> bool:
        return self._trading_mode == "demo" and int(review.get("no_trade_blocked_count") or 0) >= 3

    def _default_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        context_changes = self._external_context_proposed_changes(review)
        if self._is_no_trade_mitigation_candidate(review):
            changes = [
                {
                    "file": ".env",
                    "parameter": "NO_TRADE_RELAX_MIN_SCORE",
                    "current_value": 0.30,
                    "proposed_value": 0.18,
                    "reason": (
                        "AUTO_MIN_SIGNAL_LEVEL/FEE_ADJUSTED_EDGE_LIMIT 차단이 반복되어 "
                        "demo weak 신호 완화 기준을 최근 로그 점수대에 맞춥니다."
                    ),
                },
                {
                    "file": "app/services/trading/auto.py",
                    "parameter": "DEMO_FEE_EDGE_RELAXATION",
                    "current_value": False,
                    "proposed_value": True,
                    "reason": "demo no-trade 완화 시 수수료 보정 엣지 차단을 재평가해 0원 주문 차단을 해소합니다.",
                },
            ]
            return (context_changes + changes)[: self._config.max_params_per_run]
        if context_changes:
            return context_changes[: self._config.max_params_per_run]
        return [
            {
                "file": "STRATEGY_SPEC.md",
                "parameter": "rule_review_candidate",
                "current_value": None,
                "proposed_value": "pending_codex_patch",
                "reason": "학습 로그 분석 후 Codex가 제한된 변경안을 작성해야 합니다.",
            },
        ]

    def _external_context_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        summary = review.get("external_context_summary")
        if not isinstance(summary, dict) or int(summary.get("sample_count") or 0) <= 0:
            return []
        avg_weight = self._float(summary.get("avg_learning_weight"), 1.0)
        etf_counts = summary.get("etf_state_counts") if isinstance(summary.get("etf_state_counts"), dict) else {}
        onchain_counts = (
            summary.get("onchain_state_counts") if isinstance(summary.get("onchain_state_counts"), dict) else {}
        )
        exchange_counts = (
            summary.get("onchain_exchange_netflow_counts")
            if isinstance(summary.get("onchain_exchange_netflow_counts"), dict)
            else {}
        )
        etf_flow_total = self._float(summary.get("etf_flow_usd_total"), 0.0)
        risk_on = int(etf_counts.get("inflow", 0)) + int(onchain_counts.get("bullish", 0)) + int(exchange_counts.get("outflow", 0))
        risk_off = int(etf_counts.get("outflow", 0)) + int(onchain_counts.get("bearish", 0)) + int(exchange_counts.get("inflow", 0))
        if avg_weight > 1.03 or risk_on > risk_off:
            return [
                {
                    "file": "app/services/trading/decision.py",
                    "parameter": "EXTERNAL_CONTEXT_BULLISH_BOOST",
                    "current_value": "not_applied",
                    "proposed_value": f"signal_score_x{avg_weight}",
                    "reason": (
                        "학습 로그의 온체인/ETF 컨텍스트가 위험선호 우위입니다. "
                        f"ETF 순흐름 합계 {round(etf_flow_total, 2)} USD와 평균 가중치 {avg_weight}를 진입 점수에 반영합니다."
                    ),
                },
                {
                    "file": "app/services/trading/auto.py",
                    "parameter": "EXTERNAL_CONTEXT_POSITION_SCALING",
                    "current_value": "1.0",
                    "proposed_value": avg_weight,
                    "reason": "학습 데이터의 외부 컨텍스트 가중치로 매매 판단을 보정해 상승 컨텍스트에서 기회를 놓치지 않도록 합니다.",
                },
            ]
        if avg_weight < 0.97 or risk_off > risk_on:
            return [
                {
                    "file": "app/services/trading/decision.py",
                    "parameter": "EXTERNAL_CONTEXT_RISK_OFF",
                    "current_value": "not_applied",
                    "proposed_value": f"signal_score_x{avg_weight}",
                    "reason": (
                        "학습 로그의 온체인/ETF 컨텍스트가 위험회피 우위입니다. "
                        f"ETF 순흐름 합계 {round(etf_flow_total, 2)} USD와 평균 가중치 {avg_weight}를 진입 점수에 반영합니다."
                    ),
                },
                {
                    "file": "app/services/trading/auto.py",
                    "parameter": "EXTERNAL_CONTEXT_POSITION_SCALING",
                    "current_value": "1.0",
                    "proposed_value": avg_weight,
                    "reason": "ETF 순유출/온체인 약세 구간에서 진입 강도를 낮춰 손실 가능성을 줄입니다.",
                },
            ]
        return []

    @staticmethod
    def _float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
