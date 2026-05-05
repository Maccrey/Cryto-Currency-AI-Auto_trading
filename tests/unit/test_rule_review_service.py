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


def test_rule_proposal_rejects_too_many_parameter_changes(tmp_path: Path) -> None:
    service = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=1,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )
    review = service.review()

    proposal = service.create_proposal(
        review_id=str(review["review"]["id"]),
        proposed_changes=[
            {"parameter": "BUY_RATIO_MEDIUM", "proposed_value": 0.16},
            {"parameter": "STOP_LOSS_MEDIUM", "proposed_value": 0.01},
        ],
    )

    assert proposal["proposal"]["status"] == "blocked"
    assert "too_many_parameter_changes" in proposal["proposal"]["rejection_reasons"]
    assert len(proposal["proposal"]["codex_suggested_changes"]) == 1


def test_replay_verification_allows_demo_apply_for_valid_proposal(tmp_path: Path) -> None:
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
    replay = service.verify_replay(str(proposal["proposal"]["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    result = service.apply_demo(str(proposal["proposal"]["id"]))

    assert replay["proposal"]["replay_result"]["status"] == "passed"
    assert replay["proposal"]["replay_result"]["signal_count"] == 2
    assert result["proposal"]["demo_applied"] is True
    assert result["proposal"]["status"] == "demo_applied"


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


def test_rule_review_state_persists_across_service_instances(tmp_path: Path) -> None:
    config = RuleReviewConfig(
        enabled=True,
        window_days=14,
        min_trades=0,
        min_stoplosses=0,
        max_params_per_run=3,
        apply_target="demo",
        require_manual_approval=True,
    )
    first = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=config,
    )

    review = first.review()
    proposal = first.create_proposal(review_id=str(review["review"]["id"]))
    first.verify_replay(str(proposal["proposal"]["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    first.apply_demo(str(proposal["proposal"]["id"]))

    second = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=config,
    )
    restored = second.get_proposal(str(proposal["proposal"]["id"]))

    assert restored["proposal"]["id"] == proposal["proposal"]["id"]
    assert restored["proposal"]["status"] == "demo_applied"
    assert restored["proposal"]["replay_result"]["status"] == "passed"
    assert (tmp_path / "rule-review-state.json").exists()
