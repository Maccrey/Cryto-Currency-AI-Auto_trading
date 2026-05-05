from pathlib import Path

from app.services.rules.review import RuleReviewConfig, RuleReviewService


def test_rule_proposal_is_blocked_when_trade_sample_is_too_small(tmp_path: Path) -> None:
    service = RuleReviewService(
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
        ),
    )

    review = service.review()
    proposal = service.create_proposal(review_id=str(review["review"]["id"]))

    assert proposal["proposal"]["status"] == "blocked"
    assert "insufficient_trade_sample" in proposal["proposal"]["rejection_reasons"]
    assert "insufficient_stoploss_sample" in proposal["proposal"]["rejection_reasons"]


def test_rule_proposal_requires_replay_before_demo_apply(tmp_path: Path) -> None:
    service = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()
    proposal = service.create_proposal(review_id=str(review["review"]["id"]))
    result = service.apply_demo(str(proposal["proposal"]["id"]))

    assert result["proposal"]["demo_applied"] is False
    assert "replay_required" in result["proposal"]["rejection_reasons"]


def test_live_approval_requires_demo_apply_and_manual_approval(tmp_path: Path) -> None:
    service = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()
    proposal = service.create_proposal(review_id=str(review["review"]["id"]))
    result = service.approve_live(str(proposal["proposal"]["id"]), approved_by="")

    assert result["proposal"]["live_approved"] is False
    assert "demo_apply_required" in result["proposal"]["rejection_reasons"]
    assert "manual_approval_required" in result["proposal"]["rejection_reasons"]
