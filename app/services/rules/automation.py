from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.learning.model_readiness import ModelTrainingReadinessService
from app.services.rules.review import RuleReviewService

logger = logging.getLogger(__name__)


class AutoRuleUpdateService:
    """Run the Codex rule improvement pipeline once learning readiness reaches 100%."""

    def __init__(
        self,
        *,
        readiness_service: ModelTrainingReadinessService,
        rule_review_service: RuleReviewService,
        fixture_path: Path,
        no_trade_trigger_hours: float = 24.0,
    ) -> None:
        self._readiness_service = readiness_service
        self._rule_review_service = rule_review_service
        self._fixture_path = fixture_path
        self._no_trade_trigger_hours = max(float(no_trade_trigger_hours), 0.0)
        self._last_applied_readiness_key: str | None = None
        self._running = False
        self._last_no_trade_trigger_key: str | None = None

    def maybe_run(self) -> dict[str, object]:
        config = getattr(self._rule_review_service, "_config", None)
        if config is not None and not bool(getattr(config, "auto_update_enabled", False)):
            return {"status": "skipped", "reason": "auto_rule_update_disabled"}
        if self._running:
            return {"status": "skipped", "reason": "auto_rule_update_running"}
        readiness = self._readiness_service.build()
        no_trade_trigger = self._no_trade_trigger(readiness)
        completion_rate = float(readiness.get("completion_rate") or 0.0)
        if completion_rate < 1.0 and no_trade_trigger is None:
            return {
                "status": "skipped",
                "reason": "learning_completion_incomplete",
                "completion_rate": readiness.get("completion_rate", 0.0),
            }
        readiness_key = self._readiness_key(readiness)
        if no_trade_trigger is not None:
            readiness_key = "no_trade_24h|{}|{}|{}".format(
                readiness_key,
                no_trade_trigger.get("last_trade_at"),
                no_trade_trigger.get("reference_at"),
            )
            if readiness_key == self._last_no_trade_trigger_key:
                return {
                    "status": "skipped",
                    "reason": "already_applied_no_trade_24h",
                    "completion_rate": completion_rate,
                    "no_trade_trigger": no_trade_trigger,
                }
        elif readiness_key == self._last_applied_readiness_key:
            return {"status": "skipped", "reason": "already_applied", "completion_rate": 1.0}
        self._running = True
        try:
            result = self._rule_review_service.auto_improve(
                fixture_path=self._fixture_path,
                force=True,
                trigger_reason="no_trade_24h" if no_trade_trigger is not None else "learning_ready",
            )
        except Exception as exc:
            logger.exception("auto_rule_update_failed")
            return {"status": "failed", "reason": str(exc), "completion_rate": 1.0}
        finally:
            self._running = False
        proposal = result.get("proposal")
        rejection_reasons = (
            proposal.get("rejection_reasons", [])
            if isinstance(proposal, dict)
            else []
        )
        reset_learning_completion = self._should_reset_learning_completion(
            status=str(result.get("status", "")),
            rejection_reasons=[str(reason) for reason in rejection_reasons],
        )
        if reset_learning_completion:
            if no_trade_trigger is not None:
                self._last_no_trade_trigger_key = readiness_key
            else:
                self._last_applied_readiness_key = readiness_key
        elif no_trade_trigger is not None and str(result.get("status", "")) != "failed":
            self._last_no_trade_trigger_key = readiness_key
        return {
            "status": result.get("status", "unknown"),
            "reason": None,
            "completion_rate": completion_rate,
            "reset_learning_completion": reset_learning_completion,
            "no_trade_trigger": no_trade_trigger,
            "rule_changed": bool(isinstance(proposal, dict) and proposal.get("demo_applied")),
            "result": result,
        }

    def _no_trade_trigger(self, readiness: dict[str, Any]) -> dict[str, object] | None:
        if self._no_trade_trigger_hours <= 0:
            return None
        metrics = readiness.get("metrics") if isinstance(readiness.get("metrics"), dict) else {}
        if int(metrics.get("blocked_cycles", 0) or 0) <= 0:
            return None
        reference_at = self._parse_datetime(readiness.get("latest_event_at")) or datetime.now(UTC)
        last_trade_at = self._parse_datetime(readiness.get("last_trade_at"))
        first_event_at = self._parse_datetime(readiness.get("first_event_at"))
        baseline_at = last_trade_at or first_event_at
        if baseline_at is None:
            return None
        hours_without_trade = (reference_at - baseline_at).total_seconds() / 3600
        if hours_without_trade < self._no_trade_trigger_hours:
            return None
        return {
            "reason": "no_trade_24h",
            "threshold_hours": self._no_trade_trigger_hours,
            "hours_without_trade": round(hours_without_trade, 3),
            "last_trade_at": None if last_trade_at is None else last_trade_at.isoformat(),
            "reference_at": reference_at.isoformat(),
            "blocked_cycles": int(metrics.get("blocked_cycles", 0) or 0),
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
    def _readiness_key(readiness: dict[str, Any]) -> str:
        metrics = readiness.get("metrics")
        if not isinstance(metrics, dict):
            return "unknown"
        return "|".join(f"{key}={metrics.get(key, 0)}" for key in sorted(metrics))

    @staticmethod
    def _should_reset_learning_completion(
        *,
        status: str,
        rejection_reasons: list[str],
    ) -> bool:
        if status == "completed":
            return True
        return "win_rate_above_auto_update_threshold" in rejection_reasons
