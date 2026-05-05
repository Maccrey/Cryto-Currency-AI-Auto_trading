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


class RuleReviewService:
    """Build rule improvement reviews and guard proposal promotion steps."""

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
            "external_context_summary": review.get("external_context_summary", self._empty_external_context_summary()),
            "codex_suggested_changes": changes,
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
            "change_reason": "; ".join(change_reasons) or "학습 로그 기반 Codex 룰 개선 파이프라인 이벤트",
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
            "commit_hash": "",
        }
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

    def _collect_metrics(self) -> dict[str, object]:
        trade_count = 0
        stop_loss_count = 0
        cause_counts: dict[str, int] = {}
        context_samples: list[dict[str, Any]] = []
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
                if event_name == "stop_loss_triggered" or payload.get("is_stop_loss"):
                    stop_loss_count += 1
                    reason = str(payload.get("reason_code") or payload.get("stop_loss_reason") or "unknown")
                    cause_counts[reason] = cause_counts.get(reason, 0) + 1
                context = payload.get("external_context") if event_name == "auto_trade_cycle" else payload
                if event_name in {"auto_trade_cycle", "external_market_context_snapshot"} and isinstance(context, dict):
                    context_samples.append(context)
        causes = [
            {"reason": reason, "count": count}
            for reason, count in sorted(cause_counts.items(), key=lambda item: item[1], reverse=True)
        ]
        return {
            "trade_count": trade_count,
            "stop_loss_count": stop_loss_count,
            "major_loss_causes": causes[:5],
            "external_context_summary": self._external_context_summary(context_samples),
        }

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
        etf_counts: Counter[str] = Counter()
        weights: list[float] = []
        for sample in samples:
            onchain = sample.get("onchain") or {}
            etf = sample.get("etf") or {}
            if isinstance(onchain, dict):
                onchain_counts.update([str(onchain.get("state") or "unknown")])
            if isinstance(etf, dict):
                etf_counts.update([str(etf.get("state") or "unknown")])
            try:
                weights.append(float(sample.get("learning_weight", 1.0)))
            except (TypeError, ValueError):
                pass
        return {
            "sample_count": len(samples),
            "onchain_state_counts": dict(onchain_counts),
            "etf_state_counts": dict(etf_counts),
            "avg_learning_weight": round(sum(weights) / len(weights), 3) if weights else 1.0,
        }

    @staticmethod
    def _empty_external_context_summary() -> dict[str, object]:
        return {
            "sample_count": 0,
            "onchain_state_counts": {},
            "etf_state_counts": {},
            "avg_learning_weight": 1.0,
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
