from __future__ import annotations

import logging
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
    ) -> None:
        self._readiness_service = readiness_service
        self._rule_review_service = rule_review_service
        self._fixture_path = fixture_path
        self._last_applied_readiness_key: str | None = None
        self._running = False

    def maybe_run(self) -> dict[str, object]:
        config = getattr(self._rule_review_service, "_config", None)
        if config is not None and not bool(getattr(config, "auto_update_enabled", False)):
            return {"status": "skipped", "reason": "auto_rule_update_disabled"}
        if self._running:
            return {"status": "skipped", "reason": "auto_rule_update_running"}
        readiness = self._readiness_service.build()
        if float(readiness.get("completion_rate") or 0.0) < 1.0:
            return {
                "status": "skipped",
                "reason": "learning_completion_incomplete",
                "completion_rate": readiness.get("completion_rate", 0.0),
            }
        readiness_key = self._readiness_key(readiness)
        if readiness_key == self._last_applied_readiness_key:
            return {"status": "skipped", "reason": "already_applied", "completion_rate": 1.0}
        self._running = True
        try:
            result = self._rule_review_service.auto_improve(fixture_path=self._fixture_path, force=True)
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
            self._last_applied_readiness_key = readiness_key
        return {
            "status": result.get("status", "unknown"),
            "reason": None,
            "completion_rate": 1.0,
            "reset_learning_completion": reset_learning_completion,
            "rule_changed": bool(isinstance(proposal, dict) and proposal.get("demo_applied")),
            "result": result,
        }

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
