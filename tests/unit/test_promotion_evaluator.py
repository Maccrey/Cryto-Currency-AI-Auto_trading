from __future__ import annotations

from app.services.promotion.evaluator import PromotionEvaluation, PromotionEvaluator


def test_promotion_evaluator_marks_ready_when_all_thresholds_pass() -> None:
    evaluator = PromotionEvaluator(
        min_demo_days=14,
        min_trades=100,
        min_profit_factor=1.2,
        max_drawdown=0.08,
        max_stoploss_failures=0,
    )

    evaluation = evaluator.evaluate(
        demo_days=16,
        total_trades=132,
        profit_factor=1.31,
        max_drawdown=0.051,
        stoploss_failures=0,
    )

    assert evaluation == PromotionEvaluation(
        status="READY_FOR_REVIEW",
        approved=False,
        rejection_reasons=[],
    )


def test_promotion_evaluator_rejects_when_metrics_are_below_threshold() -> None:
    evaluator = PromotionEvaluator(
        min_demo_days=14,
        min_trades=100,
        min_profit_factor=1.2,
        max_drawdown=0.08,
        max_stoploss_failures=0,
    )

    evaluation = evaluator.evaluate(
        demo_days=7,
        total_trades=64,
        profit_factor=1.08,
        max_drawdown=0.11,
        stoploss_failures=2,
    )

    assert evaluation == PromotionEvaluation(
        status="NOT_READY",
        approved=False,
        rejection_reasons=[
            "DEMO_DAYS_BELOW_THRESHOLD",
            "TRADE_COUNT_BELOW_THRESHOLD",
            "PROFIT_FACTOR_BELOW_THRESHOLD",
            "MAX_DRAWDOWN_ABOVE_THRESHOLD",
            "STOPLOSS_FAILURES_ABOVE_THRESHOLD",
        ],
    )

