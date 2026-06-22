from __future__ import annotations

import json
import logging
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.learning.jsonl import iter_jsonl_objects
from app.services.replay.harness import ReplayHarness
from app.services.replay.loader import ReplayFixtureLoader

logger = logging.getLogger(__name__)


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
        telegram_gateway: Any | None = None,
        demo_rule_reset_callback: Any | None = None,
    ) -> None:
        self._market = market
        self._trade_coin = (trade_coin or market.split("-")[-1]).upper()
        self._trading_mode = trading_mode
        self._learning_log_dir = learning_log_dir
        self._config = config
        self._telegram_gateway = telegram_gateway
        self._demo_rule_reset_callback = demo_rule_reset_callback
        self._state_path = self._learning_log_dir / "rule-review-state.json"
        self._history_path = self._learning_log_dir / "rule-change-history.jsonl"
        self._learning_md_path = self._learning_log_dir / "rule-improvement-learning.md"
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
            "rule_variant_shadow_summary": metrics["rule_variant_shadow_summary"],
            "technical_indicator_summary": metrics["technical_indicator_summary"],
            "market_data_quality_summary": metrics["market_data_quality_summary"],
            "trade_staleness_summary": metrics["trade_staleness_summary"],
            "codex_rule_prompt": self._build_codex_rule_prompt(metrics),
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
            "rule_variant_shadow_summary": review.get(
                "rule_variant_shadow_summary",
                self._empty_rule_variant_shadow_summary(),
            ),
            "technical_indicator_summary": review.get(
                "technical_indicator_summary",
                self._empty_technical_indicator_summary(),
            ),
            "market_data_quality_summary": review.get(
                "market_data_quality_summary",
                self._empty_market_data_quality_summary(),
            ),
            "trade_staleness_summary": review.get(
                "trade_staleness_summary",
                self._empty_trade_staleness_summary(),
            ),
            "codex_rule_prompt": review.get("codex_rule_prompt", ""),
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

    def auto_improve(
        self,
        *,
        fixture_path: Path,
        force: bool = False,
        trigger_reason: str = "manual",
    ) -> dict[str, object]:
        steps: list[dict[str, object]] = []

        review_response = self.review()
        review = review_response["review"]
        auto_gate_reasons = self._auto_update_gate_reasons(review)
        if force:
            auto_gate_reasons = [
                reason
                for reason in auto_gate_reasons
                if reason != "learning_completion_incomplete"
            ]
        steps.append(
            {
                "name": "Codex CLI 룰 개선 하네스 시작",
                "status": "blocked" if auto_gate_reasons else "completed",
                "message": (
                    "자동 룰 업데이트 조건을 충족하지 못했습니다: " + ", ".join(auto_gate_reasons)
                    if auto_gate_reasons
                    else f"학습 로그 기반 자동 룰 개선 파이프라인을 시작했습니다. 트리거={trigger_reason}"
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
        if bool(proposal.get("demo_applied")):
            self._notify_rule_improved(proposal=proposal, final_summary=final_summary)
        return {
            "status": "blocked" if auto_gate_reasons else ("completed" if demo_applied else "needs_retry"),
            "codex_cli": {
                "mode": "local_harness",
                "command": "codex rule-improve --from-learning-log --replay --apply-demo",
                "prompt": review.get("codex_rule_prompt", ""),
            },
            "steps": steps,
            "trigger_reason": trigger_reason,
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
        loader = ReplayFixtureLoader()
        ticks = loader.load(fixture_path)
        observation_ticks = loader.load_market_observations(self._learning_log_dir / "market-observations.jsonl")
        if len(observation_ticks) >= 4:
            ticks = observation_ticks
        harness = ReplayHarness()
        results = harness.run(ticks)
        replay_summary = harness.summarize(results)
        blocked_count = replay_summary.blocked_count
        signal_count = replay_summary.signal_count
        passed = (
            signal_count > 0
            and blocked_count < signal_count
            and replay_summary.trade_count > 0
            and replay_summary.final_profit_rate > 0.0
            and replay_summary.profit_guard_status == "passed"
        )
        proposal["replay_result"] = {
            "status": "passed" if passed else "failed",
            "fixture_path": str(fixture_path),
            "source": "market_observations" if len(observation_ticks) >= 4 else "fixture",
            "signal_count": signal_count,
            "blocked_count": blocked_count,
            "trade_count": replay_summary.trade_count,
            "final_equity": replay_summary.final_equity,
            "final_profit_rate": replay_summary.final_profit_rate,
            "max_drawdown_pct": replay_summary.max_drawdown_pct,
            "profit_guard_status": replay_summary.profit_guard_status,
            "max_signal_score": replay_summary.max_signal_score,
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
        elif float(proposal["replay_result"].get("final_profit_rate") or 0.0) <= 0.0:
            reasons.add("replay_non_positive_profit")
        elif int(proposal["replay_result"].get("trade_count") or 0) <= 0:
            reasons.add("replay_no_trades")
        shadow_summary = proposal.get("rule_variant_shadow_summary")
        if (
            isinstance(shadow_summary, dict)
            and int(shadow_summary.get("sample_count") or 0) > 0
            and not shadow_summary.get("best_positive_variant_key")
        ):
            reasons.add("shadow_no_positive_variant")
        if proposal["status"] == "blocked":
            reasons.add("proposal_blocked")
        proposal["rejection_reasons"] = sorted(reasons)
        proposal["demo_applied"] = not proposal["rejection_reasons"]
        if proposal["demo_applied"]:
            proposal["status"] = "demo_applied"
            proposal["demo_applied_at"] = datetime.now(UTC).isoformat()
            if self._demo_rule_reset_callback is not None:
                self._demo_rule_reset_callback()
                proposal["rule_variant_shadow_reset"] = True
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
            "rule_variant_shadow_summary": proposal.get(
                "rule_variant_shadow_summary",
                self._empty_rule_variant_shadow_summary(),
            ),
            "technical_indicator_summary": proposal.get(
                "technical_indicator_summary",
                self._empty_technical_indicator_summary(),
            ),
            "market_data_quality_summary": proposal.get(
                "market_data_quality_summary",
                self._empty_market_data_quality_summary(),
            ),
            "trade_staleness_summary": proposal.get(
                "trade_staleness_summary",
                self._empty_trade_staleness_summary(),
            ),
            "previous_rule_snapshot": self._previous_rule_snapshot(changes),
            "proposed_rule_snapshot": self._proposed_rule_snapshot(changes),
            "changed_parameters": self._changed_parameters(changes),
            "optimization_tracking": self._optimization_tracking_summary(proposal=proposal, changes=changes),
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
        self._append_learning_markdown(history)

    def _append_learning_markdown(self, history: dict[str, Any]) -> None:
        self._learning_log_dir.mkdir(parents=True, exist_ok=True)
        if not self._learning_md_path.exists():
            self._learning_md_path.write_text(
                "\n".join(
                    [
                        "# 룰 개선 학습 기록",
                        "",
                        "자동 룰 개선 과정의 이유, 검증 결과, 적용 결과를 다음 개선에 참고하기 위해 누적한다.",
                        "",
                    ],
                ),
                encoding="utf-8",
            )
        changed_parameters = history.get("changed_parameters") or []
        replay_result = history.get("replay_result") or {}
        demo_result = history.get("demo_result") or {}
        lines = [
            f"## {history.get('created_at', '-')}",
            "",
            f"- 이벤트: {history.get('event_type', '-')}",
            f"- 제안 ID: {history.get('proposal_id', '-')}",
            f"- 시장/코인: {history.get('market', '-')} / {history.get('trade_coin', '-')}",
            f"- 적용 대상: {history.get('applied_target', '-')}",
            f"- 승인 상태: {history.get('approval_status', '-')}",
            f"- 변경 항목: {', '.join(str(item) for item in changed_parameters) if changed_parameters else '없음'}",
            f"- 최적화 추적: {json.dumps(history.get('optimization_tracking', {}), ensure_ascii=False, sort_keys=True)}",
            f"- 변경 이유: {history.get('change_reason', '-')}",
            f"- 기대 효과: {history.get('expected_effect', '-')}",
            f"- 알려진 리스크: {history.get('known_risks', '-')}",
            f"- Replay 결과: {json.dumps(replay_result, ensure_ascii=False, sort_keys=True) if replay_result else '없음'}",
            f"- Demo 적용 결과: {json.dumps(demo_result, ensure_ascii=False, sort_keys=True)}",
            f"- 차단/경고: {', '.join(str(item) for item in history.get('blocked_reason_summary', [])) or '없음'}",
            f"- A-O 15개 룰 동시 테스트: {json.dumps(history.get('rule_variant_shadow_summary', {}), ensure_ascii=False, sort_keys=True)}",
            f"- 전문 보조지표 요약: {json.dumps(history.get('technical_indicator_summary', {}), ensure_ascii=False, sort_keys=True)}",
            f"- 시장 데이터 품질: {json.dumps(history.get('market_data_quality_summary', {}), ensure_ascii=False, sort_keys=True)}",
            "",
        ]
        with self._learning_md_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(lines))

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

    def _notify_rule_improved(
        self,
        *,
        proposal: dict[str, Any],
        final_summary: dict[str, object],
    ) -> None:
        if self._telegram_gateway is None:
            return
        try:
            changed_parameters = final_summary.get("changed_parameters") or []
            change_text = ", ".join(str(item) for item in changed_parameters) or "변경 항목 없음"
            self._telegram_gateway.send_message(
                "\n".join(
                    [
                        "자동 룰 개선이 적용되었습니다.",
                        f"거래 시장은 {self._market}이고 적용 대상은 {proposal.get('apply_target', 'demo')}입니다.",
                        f"변경 항목: {change_text}",
                        f"변경 사유: {final_summary.get('change_reason', '-')}",
                        "새 룰은 즉시 다음 자동매매 판단부터 반영됩니다.",
                    ],
                ),
            )
        except Exception:
            logger.exception("telegram_rule_improvement_notification_failed")

    def _collect_metrics(self) -> dict[str, object]:
        fill_trade_count = 0
        exit_trade_count = 0
        fill_stop_loss_count = 0
        exit_stop_loss_count = 0
        triggered_stop_loss_count = 0
        cause_counts: dict[str, int] = {}
        exit_cause_counts: dict[str, int] = {}
        triggered_cause_counts: dict[str, int] = {}
        blocked_reasons: Counter[str] = Counter()
        sizing_blocked_reasons: Counter[str] = Counter()
        sample_limit = 5000
        context_samples: deque[dict[str, Any]] = deque(maxlen=sample_limit)
        rule_variant_shadow_samples: deque[dict[str, Any]] = deque(maxlen=sample_limit)
        technical_indicator_samples: deque[dict[str, Any]] = deque(maxlen=sample_limit)
        market_feature_samples: deque[dict[str, Any]] = deque(maxlen=sample_limit)
        market_window_samples: deque[dict[str, Any]] = deque(maxlen=sample_limit)
        latest_event_at: datetime | None = None
        last_trade_at: datetime | None = None
        completion_rates: list[float] = []
        fill_closed_trade_pnls: list[float] = []
        exit_closed_trade_pnls: list[float] = []
        last_fill_sell_pnl: float | None = None
        log_path = self._learning_log_dir / "learning.jsonl"
        if log_path.exists():
            for row in iter_jsonl_objects(log_path):
                event_name = str(row.get("event_name", ""))
                recorded_at = self._parse_datetime(row.get("recorded_at"))
                if recorded_at is not None and (latest_event_at is None or recorded_at > latest_event_at):
                    latest_event_at = recorded_at
                payload = row.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {}
                if event_name in {"fill_result", "position_opened", "position_closed", "position_exit_completed"}:
                    if recorded_at is not None and (last_trade_at is None or recorded_at > last_trade_at):
                        last_trade_at = recorded_at
                if event_name in {"fill_result", "position_closed"}:
                    if payload.get("side") == "sell" or event_name == "position_closed":
                        fill_trade_count += 1
                        try:
                            last_fill_sell_pnl = float(payload.get("pnl", payload.get("realized_pnl", 0.0)))
                            fill_closed_trade_pnls.append(last_fill_sell_pnl)
                        except (TypeError, ValueError):
                            pass
                    if bool(payload.get("is_stop_loss")):
                        fill_stop_loss_count += 1
                if event_name == "position_exit_completed":
                    exit_trade_count += 1
                    pnl_value = payload.get("pnl")
                    if pnl_value is None:
                        pnl_value = payload.get("realized_pnl")
                    if pnl_value is None:
                        pnl_value = payload.get("unrealized_return_pct")
                    if pnl_value is None:
                        pnl_value = last_fill_sell_pnl or 0.0
                    try:
                        exit_closed_trade_pnls.append(float(pnl_value))
                    except (TypeError, ValueError):
                        pass
                    last_fill_sell_pnl = None
                    if bool(payload.get("is_stop_loss")):
                        exit_stop_loss_count += 1
                        reason = str(payload.get("reason_code") or payload.get("stop_loss_reason") or "unknown")
                        exit_cause_counts[reason] = exit_cause_counts.get(reason, 0) + 1
                elif event_name == "stop_loss_triggered":
                    triggered_stop_loss_count += 1
                    reason = str(payload.get("reason_code") or payload.get("stop_loss_reason") or "unknown")
                    triggered_cause_counts[reason] = triggered_cause_counts.get(reason, 0) + 1
                if event_name == "auto_trade_cycle":
                    try:
                        completion_rates.append(float(payload.get("learning_completion_rate", 0.0)))
                    except (TypeError, ValueError):
                        pass
                    if payload.get("reason") is not None:
                        blocked_reasons.update([str(payload.get("reason"))])
                    if payload.get("sizing_blocked_reason") is not None:
                        sizing_blocked_reasons.update([str(payload.get("sizing_blocked_reason"))])
                    shadow = payload.get("rule_variant_shadow")
                    if isinstance(shadow, dict):
                        rule_variant_shadow_samples.append(shadow)
                    market_window = payload.get("market_window")
                    if isinstance(market_window, dict):
                        market_window_samples.append(market_window)
                technical_indicators = payload.get("technical_indicators")
                if event_name == "signal_generated" and isinstance(technical_indicators, dict):
                    technical_indicator_samples.append(technical_indicators)
                market_features = payload.get("market_features")
                if event_name == "signal_generated" and isinstance(market_features, dict):
                    market_feature_samples.append(market_features)
                context = payload.get("external_context") if event_name == "auto_trade_cycle" else payload
                if event_name in {"auto_trade_cycle", "external_market_context_snapshot"} and isinstance(context, dict):
                    context_samples.append(context)
        trade_count = exit_trade_count if exit_trade_count > 0 else fill_trade_count
        stop_loss_count = (
            exit_stop_loss_count
            if exit_trade_count > 0
            else triggered_stop_loss_count
            if triggered_stop_loss_count > 0
            else fill_stop_loss_count
        )
        cause_counts = (
            exit_cause_counts
            if exit_cause_counts
            else triggered_cause_counts
        )
        closed_trade_pnls = (
            exit_closed_trade_pnls
            if exit_closed_trade_pnls
            else fill_closed_trade_pnls
        )
        causes = [
            {"reason": reason, "count": count}
            for reason, count in sorted(cause_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        no_trade_blocked_count = (
            blocked_reasons.get("AUTO_MIN_SIGNAL_LEVEL", 0)
            + blocked_reasons.get("WEAK_ENTRY_HISTORICAL_LOSS_BLOCK", 0)
            + blocked_reasons.get("WEAK_SCALE_IN_HISTORICAL_LOSS_BLOCK", 0)
            + blocked_reasons.get("MARKET_STATE_BEAR_ENTRY_BLOCK", 0)
            + blocked_reasons.get("SIDEWAYS_WEAK_RELAXED_ENTRY_BLOCK", 0)
            + blocked_reasons.get("SIDEWAYS_WEAK_SCALE_IN_BLOCK", 0)
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
            "rule_variant_shadow_summary": self._rule_variant_shadow_summary(rule_variant_shadow_samples),
            "technical_indicator_summary": self._technical_indicator_summary(technical_indicator_samples),
            "market_data_quality_summary": self._market_data_quality_summary(
                market_feature_samples=market_feature_samples,
                market_window_samples=market_window_samples,
                observation_path=self._learning_log_dir / "market-observations.jsonl",
            ),
            "trade_staleness_summary": self._trade_staleness_summary(
                last_trade_at=last_trade_at,
                latest_event_at=latest_event_at,
            ),
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
    def _optimization_tracking_summary(*, proposal: dict[str, Any], changes: Any) -> dict[str, object]:
        changed_parameters = RuleReviewService._changed_parameters(changes)
        replay_result = proposal.get("replay_result") if isinstance(proposal.get("replay_result"), dict) else {}
        return {
            "schema_version": 1,
            "tracking_goal": "compare_rule_update_effect_in_next_reviews",
            "changed_parameters": changed_parameters,
            "baseline": {
                "trade_count": proposal.get("trade_count"),
                "stop_loss_count": proposal.get("stop_loss_count"),
                "no_trade_blocked_count": proposal.get("no_trade_blocked_count"),
                "win_rate": proposal.get("win_rate"),
                "trade_staleness_summary": proposal.get(
                    "trade_staleness_summary",
                    RuleReviewService._empty_trade_staleness_summary(),
                ),
                "rule_variant_shadow_summary": proposal.get(
                    "rule_variant_shadow_summary",
                    RuleReviewService._empty_rule_variant_shadow_summary(),
                ),
            },
            "post_update_metrics_to_compare": [
                "hours_since_last_trade",
                "trade_count_delta",
                "stop_loss_count_delta",
                "no_trade_blocked_count_delta",
                "win_rate_delta",
                "replay_final_profit_rate_delta",
                "demo_realized_pnl_delta",
                "trade_logic_update_trace.applied_count",
            ],
            "latest_replay": {
                "status": replay_result.get("status"),
                "final_profit_rate": replay_result.get("final_profit_rate"),
                "max_drawdown_pct": replay_result.get("max_drawdown_pct"),
                "trade_count": replay_result.get("trade_count"),
            },
        }

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
    def _empty_trade_staleness_summary() -> dict[str, object]:
        return {
            "last_trade_at": None,
            "latest_event_at": None,
            "hours_since_last_trade": None,
            "no_trade_24h": False,
        }

    @staticmethod
    def _trade_staleness_summary(
        *,
        last_trade_at: datetime | None,
        latest_event_at: datetime | None,
    ) -> dict[str, object]:
        if latest_event_at is None:
            return RuleReviewService._empty_trade_staleness_summary()
        hours_since_last_trade = None
        if last_trade_at is not None:
            hours_since_last_trade = round((latest_event_at - last_trade_at).total_seconds() / 3600, 3)
        return {
            "last_trade_at": None if last_trade_at is None else last_trade_at.isoformat(),
            "latest_event_at": latest_event_at.isoformat(),
            "hours_since_last_trade": hours_since_last_trade,
            "no_trade_24h": hours_since_last_trade is not None and hours_since_last_trade >= 24.0,
        }

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

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
    def _empty_rule_variant_shadow_summary() -> dict[str, object]:
        return {
            "sample_count": 0,
            "leader_counts": {},
            "best_variant_key": None,
            "best_variant_label": None,
            "avg_profit_rate_by_variant": {},
            "best_positive_variant_key": None,
            "best_positive_variant_label": None,
            "positive_variant_keys": [],
            "latest_results": [],
        }

    @staticmethod
    def _empty_technical_indicator_summary() -> dict[str, object]:
        return {
            "sample_count": 0,
            "avg_rsi_14": 50.0,
            "avg_macd_histogram": 0.0,
            "avg_bollinger_position": 0.5,
            "avg_ma_trend": 0.0,
            "avg_stochastic_k": 50.0,
            "avg_price_position_20": 0.5,
            "avg_drawdown_from_high_20": 0.0,
            "avg_rebound_from_low_20": 0.0,
            "avg_trend_efficiency_20": 0.0,
            "overbought_count": 0,
            "oversold_count": 0,
            "low_rebound_confirmation_count": 0,
            "high_position_reversal_risk_count": 0,
            "bullish_momentum_count": 0,
            "bearish_momentum_count": 0,
        }

    @staticmethod
    def _empty_market_data_quality_summary() -> dict[str, object]:
        return {
            "feature_sample_count": 0,
            "window_sample_count": 0,
            "raw_observation_count": 0,
            "avg_price_change_pct": 0.0,
            "avg_traded_value_multiple": 1.0,
            "avg_orderbook_imbalance": 0.0,
            "avg_spread_bps": 0.0,
            "avg_short_volatility": 0.0,
            "quality_level": "insufficient",
        }

    @staticmethod
    def _market_data_quality_summary(
        *,
        market_feature_samples: list[dict[str, Any]],
        market_window_samples: list[dict[str, Any]],
        observation_path: Path,
    ) -> dict[str, object]:
        feature_count = len(market_feature_samples)
        window_count = len(market_window_samples)
        raw_count = RuleReviewService._line_count(observation_path)
        if feature_count == 0 and window_count == 0 and raw_count == 0:
            return RuleReviewService._empty_market_data_quality_summary()
        price_changes = RuleReviewService._float_values(market_window_samples, "price_change_pct")
        traded_value_multiples = (
            RuleReviewService._float_values(market_feature_samples, "traded_value_multiple")
            + RuleReviewService._float_values(market_window_samples, "traded_value_multiple")
        )
        imbalances = RuleReviewService._float_values(market_feature_samples, "orderbook_imbalance")
        spreads = RuleReviewService._float_values(market_feature_samples, "spread_bps")
        volatility = RuleReviewService._float_values(market_feature_samples, "short_volatility")
        total_signal = feature_count + window_count + raw_count
        quality_level = "strong" if total_signal >= 500 else ("usable" if total_signal >= 80 else "thin")
        return {
            "feature_sample_count": feature_count,
            "window_sample_count": window_count,
            "raw_observation_count": raw_count,
            "avg_price_change_pct": RuleReviewService._average(price_changes, 0.0),
            "avg_traded_value_multiple": RuleReviewService._average(traded_value_multiples, 1.0),
            "avg_orderbook_imbalance": RuleReviewService._average(imbalances, 0.0),
            "avg_spread_bps": RuleReviewService._average(spreads, 0.0),
            "avg_short_volatility": RuleReviewService._average(volatility, 0.0),
            "quality_level": quality_level,
        }

    @staticmethod
    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.open("r", encoding="utf-8") if line.strip())

    @staticmethod
    def _technical_indicator_summary(samples: list[dict[str, Any]]) -> dict[str, object]:
        if not samples:
            return RuleReviewService._empty_technical_indicator_summary()
        rsi_values = RuleReviewService._float_values(samples, "rsi_14")
        macd_values = RuleReviewService._float_values(samples, "macd_histogram")
        bollinger_values = RuleReviewService._float_values(samples, "bollinger_position")
        ma_values = RuleReviewService._float_values(samples, "ma_trend")
        stochastic_values = RuleReviewService._float_values(samples, "stochastic_k")
        price_position_values = RuleReviewService._float_values(samples, "price_position_20")
        drawdown_values = RuleReviewService._float_values(samples, "drawdown_from_high_20")
        rebound_values = RuleReviewService._float_values(samples, "rebound_from_low_20")
        trend_efficiency_values = RuleReviewService._float_values(samples, "trend_efficiency_20")
        return {
            "sample_count": len(samples),
            "avg_rsi_14": RuleReviewService._average(rsi_values, 50.0),
            "avg_macd_histogram": RuleReviewService._average(macd_values, 0.0),
            "avg_bollinger_position": RuleReviewService._average(bollinger_values, 0.5),
            "avg_ma_trend": RuleReviewService._average(ma_values, 0.0),
            "avg_stochastic_k": RuleReviewService._average(stochastic_values, 50.0),
            "avg_price_position_20": RuleReviewService._average(price_position_values, 0.5),
            "avg_drawdown_from_high_20": RuleReviewService._average(drawdown_values, 0.0),
            "avg_rebound_from_low_20": RuleReviewService._average(rebound_values, 0.0),
            "avg_trend_efficiency_20": RuleReviewService._average(trend_efficiency_values, 0.0),
            "overbought_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("rsi_14"), 50.0) >= 70.0
                and RuleReviewService._float(sample.get("bollinger_position"), 0.5) >= 0.85
            ),
            "oversold_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("rsi_14"), 50.0) <= 35.0
                and RuleReviewService._float(sample.get("stochastic_k"), 50.0) <= 30.0
            ),
            "low_rebound_confirmation_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("rebound_from_low_20"), 0.0) >= 0.003
                and RuleReviewService._float(sample.get("trend_efficiency_20"), 0.0) >= 0.15
            ),
            "high_position_reversal_risk_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("price_position_20"), 0.5) >= 0.92
                and RuleReviewService._float(sample.get("trend_efficiency_20"), 0.0) < 0.35
            ),
            "bullish_momentum_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("macd_histogram"), 0.0) > 0.0
                and RuleReviewService._float(sample.get("ma_trend"), 0.0) > 0.0
            ),
            "bearish_momentum_count": sum(
                1
                for sample in samples
                if RuleReviewService._float(sample.get("macd_histogram"), 0.0) < 0.0
                and RuleReviewService._float(sample.get("ma_trend"), 0.0) < 0.0
            ),
        }

    @staticmethod
    def _rule_variant_shadow_summary(samples: list[dict[str, Any]]) -> dict[str, object]:
        if not samples:
            return RuleReviewService._empty_rule_variant_shadow_summary()
        leader_counts: Counter[str] = Counter()
        profit_rates: dict[str, list[float]] = {}
        latest_results: list[dict[str, Any]] = []
        labels: dict[str, str] = {}
        for sample in samples:
            leader_key = sample.get("leader_key")
            if leader_key:
                leader_counts.update([str(leader_key)])
            results = sample.get("results")
            if not isinstance(results, list):
                continue
            latest_results = [item for item in results if isinstance(item, dict)]
            for item in latest_results:
                key = str(item.get("variant_key") or "")
                if not key:
                    continue
                labels[key] = str(item.get("variant_label") or key)
                try:
                    profit_rates.setdefault(key, []).append(float(item.get("profit_rate", 0.0)))
                except (TypeError, ValueError):
                    pass
        avg_profit = {
            key: round(sum(values) / len(values), 6)
            for key, values in profit_rates.items()
            if values
        }
        best_key = max(avg_profit, key=avg_profit.get) if avg_profit else None
        positive_results = [
            item
            for item in latest_results
            if bool(item.get("promotion_eligible"))
            and float(item.get("profit_rate") or 0.0) > 0.0
            and float(item.get("realized_pnl") or 0.0) > 0.0
        ]
        best_positive = (
            max(
                positive_results,
                key=lambda item: (
                    float(item.get("profit_rate") or 0.0),
                    -float(item.get("max_drawdown_pct") or 0.0),
                ),
            )
            if positive_results
            else None
        )
        return {
            "sample_count": len(samples),
            "leader_counts": dict(leader_counts),
            "best_variant_key": best_key,
            "best_variant_label": labels.get(best_key or "", best_key),
            "avg_profit_rate_by_variant": avg_profit,
            "best_positive_variant_key": None if best_positive is None else best_positive.get("variant_key"),
            "best_positive_variant_label": None if best_positive is None else best_positive.get("variant_label"),
            "positive_variant_keys": [str(item.get("variant_key")) for item in positive_results],
            "latest_results": latest_results,
        }

    @staticmethod
    def _append_float(values: list[float], value: Any) -> None:
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            pass

    @staticmethod
    def _float_values(samples: list[dict[str, Any]], key: str) -> list[float]:
        values: list[float] = []
        for sample in samples:
            RuleReviewService._append_float(values, sample.get(key))
        return values

    @staticmethod
    def _average(values: list[float], fallback: float) -> float:
        if not values:
            return fallback
        return round(sum(values) / len(values), 6)

    def _is_no_trade_mitigation_candidate(self, review: dict[str, Any]) -> bool:
        return self._trading_mode == "demo" and int(review.get("no_trade_blocked_count") or 0) >= 3

    def _default_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        context_changes = self._external_context_proposed_changes(review)
        staleness_changes = self._trade_staleness_proposed_changes(review)
        shadow_changes = self._rule_variant_shadow_proposed_changes(review)
        technical_changes = self._technical_indicator_proposed_changes(review)
        market_quality_changes = self._market_data_quality_proposed_changes(review)
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
                    "file": "app/services/trading/decision.py",
                    "parameter": "BULL_BOX_BEAR_REBOUND_SIGNAL_BOOST",
                    "current_value": "weak_signals_remain_weak",
                    "proposed_value": "promote_supported_bull_box_bear_rebound_to_medium",
                    "reason": (
                        "상승장·박스권 하단·하락장 반등 확인 구간에서도 weak/FEE_ADJUSTED_EDGE_LIMIT 차단이 반복됩니다. "
                        "기술 지표와 호가가 받쳐주는 구간만 medium으로 승격해 수익 가능한 구간을 놓치지 않도록 합니다."
                    ),
                },
                {
                    "file": "app/services/market/trend.py",
                    "parameter": "BROAD_MARKET_STATE_CLASSIFIER",
                    "current_value": "short_recent_ticks",
                    "proposed_value": "recent_medium_broad_windows",
                    "reason": "짧은 틱 변동만으로 하락장 차단이 과다 발생해 중기/광역 가격 흐름을 함께 보고 상승장·하락장·박스권을 판단합니다.",
                },
            ]
            return (staleness_changes + technical_changes + context_changes + changes)[: self._config.max_params_per_run]
        preferred_changes = staleness_changes + shadow_changes + technical_changes + market_quality_changes + context_changes
        if preferred_changes:
            return preferred_changes[: self._config.max_params_per_run]
        return [
            {
                "file": "STRATEGY_SPEC.md",
                "parameter": "rule_review_candidate",
                "current_value": None,
                "proposed_value": "pending_codex_patch",
                "reason": "학습 로그 분석 후 Codex가 제한된 변경안을 작성해야 합니다.",
            },
        ]


    def _trade_staleness_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        summary = review.get("trade_staleness_summary")
        shadow = review.get("rule_variant_shadow_summary")
        if not isinstance(summary, dict) or not bool(summary.get("no_trade_24h")):
            return []
        best_key = str(shadow.get("best_variant_key") or "") if isinstance(shadow, dict) else ""
        hours = self._float(summary.get("hours_since_last_trade"), 0.0)
        if best_key == "B":
            return [
                {
                    "file": "app/services/trading/auto.py",
                    "parameter": "BULL_TREND_WEAK_SIGNAL_RECOVERY",
                    "current_value": "historical_loss_guard_blocks_all_weak_entries",
                    "proposed_value": "allow_bull_B_leader_weak_recovery_after_no_trade",
                    "reason": (
                        f"최근 {round(hours, 1)}시간 체결이 없고 A/B/C 섀도우에서 룰 B 추세형이 우세합니다. "
                        "상승장 확인과 수수료 엣지 재평가가 동시에 맞을 때만 약한 신호 회복 진입을 허용합니다."
                    ),
                },
            ]
        return [
            {
                "file": "app/services/trading/auto.py",
                "parameter": "NO_TRADE_24H_REVIEW_TRIGGER",
                "current_value": "manual_or_learning_completion_only",
                "proposed_value": "review_logs_after_24h_without_fills",
                "reason": f"최근 {round(hours, 1)}시간 체결이 없어 차단 사유와 장세별 섀도우 성과를 재검토합니다.",
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

    def _market_data_quality_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        summary = review.get("market_data_quality_summary")
        if not isinstance(summary, dict):
            return []
        raw_count = int(summary.get("raw_observation_count") or 0)
        feature_count = int(summary.get("feature_sample_count") or 0)
        if raw_count + feature_count <= 0:
            return [
                {
                    "file": "app/services/trading/auto.py",
                    "parameter": "MARKET_OBSERVATION_LOGGING",
                    "current_value": "not_persisted",
                    "proposed_value": "persist_price_volume_feature_windows",
                    "reason": "가격 움직임과 거래량 원시 샘플이 부족해 룰 개선 재현성이 낮습니다. 별도 시장 관측 로그를 우선 축적합니다.",
                },
            ]
        traded_value_multiple = self._float(summary.get("avg_traded_value_multiple"), 1.0)
        price_change_pct = self._float(summary.get("avg_price_change_pct"), 0.0)
        changes: list[dict[str, object]] = []
        if traded_value_multiple >= 1.25 and price_change_pct > 0:
            changes.append(
                {
                    "file": "app/services/signals/engine.py",
                    "parameter": "PRICE_VOLUME_CONFIRMATION",
                    "current_value": "score_components",
                    "proposed_value": "prefer_positive_price_with_volume_expansion",
                    "reason": (
                        "최근 시장 관측에서 가격 상승과 거래대금 확장이 함께 나타납니다. "
                        "거래량이 동반된 상승 신호를 우선하도록 진입 신뢰도를 높입니다."
                    ),
                },
            )
        if traded_value_multiple >= 1.25 and price_change_pct < 0:
            changes.append(
                {
                    "file": "app/services/risk/sideways.py",
                    "parameter": "VOLUME_SPIKE_DOWNTREND_GUARD",
                    "current_value": "not_explicit",
                    "proposed_value": "block_or_reduce_on_distribution_volume",
                    "reason": (
                        "거래대금 확장이 가격 하락과 함께 나타납니다. "
                        "분배성 거래량 구간에서는 신규 진입보다 방어적 축소를 우선합니다."
                    ),
                },
            )
        return changes

    def _technical_indicator_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        summary = review.get("technical_indicator_summary")
        if not isinstance(summary, dict) or int(summary.get("sample_count") or 0) <= 0:
            return []
        sample_count = int(summary.get("sample_count") or 0)
        bullish_count = int(summary.get("bullish_momentum_count") or 0)
        bearish_count = int(summary.get("bearish_momentum_count") or 0)
        overbought_count = int(summary.get("overbought_count") or 0)
        oversold_count = int(summary.get("oversold_count") or 0)
        avg_rsi = self._float(summary.get("avg_rsi_14"), 50.0)
        avg_bollinger = self._float(summary.get("avg_bollinger_position"), 0.5)
        avg_stochastic = self._float(summary.get("avg_stochastic_k"), 50.0)
        changes: list[dict[str, object]] = []
        if bullish_count >= max(2, sample_count // 3) and avg_rsi < 72.0:
            changes.append(
                {
                    "file": "app/services/signals/engine.py",
                    "parameter": "TECHNICAL_TREND_CONFIRMATION",
                    "current_value": "partial",
                    "proposed_value": "increase_macd_ma_confirmation_weight",
                    "reason": (
                        "전문 보조지표 학습 샘플에서 MACD 히스토그램과 이동평균 기울기 동반 상승이 반복됩니다. "
                        "과매수 전까지 추세 확인 신호의 진입 신뢰도를 높입니다."
                    ),
                },
            )
        if overbought_count >= max(2, sample_count // 4) or avg_bollinger >= 0.82:
            changes.append(
                {
                    "file": "app/services/signals/engine.py",
                    "parameter": "TECHNICAL_OVERBOUGHT_RISK_FILTER",
                    "current_value": "rsi_and_bollinger_guard",
                    "proposed_value": "tighten_entry_when_rsi_bollinger_extended",
                    "reason": (
                        f"평균 RSI {round(avg_rsi, 2)}, 볼린저 위치 {round(avg_bollinger, 3)}로 상단 과열 구간이 감지됩니다. "
                        "추격 매수보다 눌림목 대기를 우선하도록 필터를 강화합니다."
                    ),
                },
            )
        if oversold_count >= max(2, sample_count // 4) and bearish_count < bullish_count:
            changes.append(
                {
                    "file": "app/services/signals/engine.py",
                    "parameter": "TECHNICAL_PULLBACK_ENTRY",
                    "current_value": "limited",
                    "proposed_value": "use_rsi_stochastic_recovery_window",
                    "reason": (
                        f"평균 스토캐스틱 {round(avg_stochastic, 2)}와 RSI 회복 구간이 반복되어 "
                        "하락 추세가 강하지 않을 때 과매도 회복 진입을 더 정교하게 반영합니다."
                    ),
                },
            )
        if bearish_count >= max(2, sample_count // 3) and bullish_count < bearish_count:
            changes.append(
                {
                    "file": "app/services/sizing/engine.py",
                    "parameter": "TECHNICAL_BEARISH_SIZE_REDUCTION",
                    "current_value": "regime_only",
                    "proposed_value": "reduce_size_when_macd_ma_bearish",
                    "reason": "MACD/이동평균 동반 약세 샘플이 우세해 하락 모멘텀에서는 진입 크기를 낮추고 매도 대응을 빠르게 합니다.",
                },
            )
        return changes

    def _rule_variant_shadow_proposed_changes(self, review: dict[str, Any]) -> list[dict[str, object]]:
        summary = review.get("rule_variant_shadow_summary")
        if not isinstance(summary, dict) or int(summary.get("sample_count") or 0) <= 0:
            return []
        best_key = str(summary.get("best_positive_variant_key") or "")
        avg_profit = summary.get("avg_profit_rate_by_variant")
        if not best_key or not isinstance(avg_profit, dict):
            return []
        
        variant_label = summary.get("best_variant_label") or best_key
        # 추세/모멘텀/돌파공격형 계열 (B, H, M, O)
        if best_key in {"B", "H", "M", "O"}:
            return [
                {
                    "file": "app/services/sizing/engine.py",
                    "parameter": "TREND_MARKET_SIZE_MULTIPLIER",
                    "current_value": "current_profile",
                    "proposed_value": "increase_when_bull_signal_strong",
                    "reason": (
                        f"다중 룰 동시 테스트에서 룰 {best_key} ({variant_label}) 평균 수익률이 우세해 "
                        f"상승장 강신호 구간의 진입 크기와 익절 보유 시간을 정교화합니다."
                    ),
                },
            ]
        # 방어/자본보전/역변동성형 계열 (C, F, N)
        elif best_key in {"C", "F", "N"}:
            return [
                {
                    "file": "app/services/sizing/engine.py",
                    "parameter": "DEFENSIVE_MARKET_SIZE_MULTIPLIER",
                    "current_value": "current_profile",
                    "proposed_value": "reduce_when_box_or_bear",
                    "reason": (
                        f"다중 룰 동시 테스트에서 룰 {best_key} ({variant_label}) 평균 수익률이 우세해 "
                        f"박스권/하락장 진입 크기를 줄이고 매도 대응을 빠르게 합니다."
                    ),
                },
            ]
        # Baseline 및 기타 (A, D, E, G, I, J, K, L 등)
        else:
            return [
                {
                    "file": "STRATEGY_SPEC.md",
                    "parameter": "BASELINE_RULE_PREFERENCE",
                    "current_value": "unknown",
                    "proposed_value": "keep_baseline_and_reduce_extra_bias",
                    "reason": f"다중 룰 동시 테스트에서 {variant_label}가 우세해 과도한 추세/방어 편향을 줄이고 기본 매수/매도 균형을 조율합니다.",
                },
            ]

    def _build_codex_rule_prompt(self, metrics: dict[str, object]) -> str:
        return "\n".join(
            [
                "너는 이 자동매매 시스템의 매매룰 개선 에이전트다.",
                "최근 학습 로그, 체결 결과, 차단 사유, 전문 보조지표, 온체인/ETF 컨텍스트, A-O 15개 룰 다중 동시 테스트 결과를 함께 사용한다.",
                "목표는 하루 0.5% 수익을 무리하게 강제하는 것이 아니라, 손실 제한을 유지하면서 기대수익이 가장 높은 룰을 제안하는 것이다.",
                "고정 손절 파라미터와 안전장치는 임의로 완화하지 않는다.",
                f"거래 수: {metrics.get('trade_count', 0)}, 손절 수: {metrics.get('stop_loss_count', 0)}, 승률: {metrics.get('win_rate', 0.0)}",
                f"차단 사유: {json.dumps(metrics.get('blocked_reason_summary', []), ensure_ascii=False, sort_keys=True)}",
                f"사이징 차단: {json.dumps(metrics.get('sizing_blocked_reason_summary', []), ensure_ascii=False, sort_keys=True)}",
                f"전문 보조지표: {json.dumps(metrics.get('technical_indicator_summary', {}), ensure_ascii=False, sort_keys=True)}",
                f"가격/거래량 데이터 품질: {json.dumps(metrics.get('market_data_quality_summary', {}), ensure_ascii=False, sort_keys=True)}",
                f"거래 공백: {json.dumps(metrics.get('trade_staleness_summary', {}), ensure_ascii=False, sort_keys=True)}",
                f"외부 컨텍스트: {json.dumps(metrics.get('external_context_summary', {}), ensure_ascii=False, sort_keys=True)}",
                f"A-O 15개 룰 동시 테스트: {json.dumps(metrics.get('rule_variant_shadow_summary', {}), ensure_ascii=False, sort_keys=True)}",
                "제안은 최대 변경 수 제한을 지키고, 변경 이유/기대효과/리스크/replay 검증 기준을 함께 남긴다.",
            ],
        )

    @staticmethod
    def _float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
