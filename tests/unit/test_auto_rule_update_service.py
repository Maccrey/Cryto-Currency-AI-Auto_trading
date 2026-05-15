from pathlib import Path

from app.services.learning.model_readiness import ModelTrainingReadinessService, ModelTrainingThresholds
from app.services.learning.service import LearningEvent, LearningService
from app.services.rules.automation import AutoRuleUpdateService
from app.services.rules.review import RuleReviewConfig, RuleReviewService


def test_auto_rule_update_service_runs_when_learning_readiness_is_complete(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(event_name="signal_generated", market="KRW-XRP", mode="demo", payload={"level": "strong"}),
            LearningEvent(event_name="fill_result", market="KRW-XRP", mode="demo", payload={"side": "buy"}),
            LearningEvent(
                event_name="position_exit_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"reason_code": "TAKE_PROFIT_TARGET_HIT"},
            ),
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "status": "blocked",
                    "reason": "AUTO_MIN_SIGNAL_LEVEL",
                    "sizing_blocked_reason": "FEE_ADJUSTED_EDGE_LIMIT",
                },
            ),
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "status": "blocked",
                    "reason": "AUTO_MIN_SIGNAL_LEVEL",
                    "sizing_blocked_reason": "FEE_ADJUSTED_EDGE_LIMIT",
                },
            ),
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "status": "blocked",
                    "reason": "AUTO_MIN_SIGNAL_LEVEL",
                    "sizing_blocked_reason": "FEE_ADJUSTED_EDGE_LIMIT",
                },
            ),
        ],
    )
    rule_review_service = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=100,
            min_stoplosses=20,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
            auto_update_enabled=True,
        ),
    )
    service = AutoRuleUpdateService(
        readiness_service=ModelTrainingReadinessService(
            log_dir=tmp_path,
            thresholds=ModelTrainingThresholds(
                min_total_events=4,
                min_signal_events=1,
                min_fill_events=1,
                min_exit_events=1,
                min_blocked_cycles=3,
            ),
        ),
        rule_review_service=rule_review_service,
        fixture_path=Path("fixtures/replay_ticks.json"),
    )

    result = service.maybe_run()
    second = service.maybe_run()

    assert result["status"] == "completed"
    assert second["status"] == "skipped"
    assert second["reason"] == "already_applied"
