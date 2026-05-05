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


def test_rule_review_lists_latest_proposals_after_reload(tmp_path: Path) -> None:
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
    first_review = first.review()
    first_proposal = first.create_proposal(review_id=str(first_review["review"]["id"]))
    second_review = first.review()
    second_proposal = first.create_proposal(review_id=str(second_review["review"]["id"]))

    second = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=config,
    )
    response = second.list_proposals(limit=1)

    assert response["count"] == 1
    assert response["proposals"][0]["id"] == second_proposal["proposal"]["id"]
    assert response["latest_proposal"]["id"] == second_proposal["proposal"]["id"]
    assert response["proposals"][0]["id"] != first_proposal["proposal"]["id"]


def test_rule_review_includes_coin_and_log_dir_metadata(tmp_path: Path) -> None:
    service = RuleReviewService(
        market="KRW-BTC",
        trade_coin="BTC",
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

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]
    proposals = service.list_proposals()

    assert review["market"] == "KRW-BTC"
    assert review["trade_coin"] == "BTC"
    assert review["learning_log_dir"] == str(tmp_path)
    assert proposal["trade_coin"] == "BTC"
    assert proposal["learning_log_dir"] == str(tmp_path)
    assert proposals["trade_coin"] == "BTC"
    assert proposals["learning_log_dir"] == str(tmp_path)


def test_rule_review_summarizes_external_market_context(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                '{"event_name":"auto_trade_cycle","payload":{"external_context":{"onchain":{"state":"bullish"},"etf":{"state":"inflow"},"learning_weight":1.2}}}',
                '{"event_name":"external_market_context_snapshot","payload":{"onchain":{"state":"bearish"},"etf":{"state":"outflow"},"learning_weight":0.8}}',
                '{"event_name":"fill_result","payload":{"is_stop_loss":true,"stop_loss_reason":"ETF_OUTFLOW"}}',
            ],
        )
        + "\n",
        encoding="utf-8",
    )
    service = RuleReviewService(
        market="KRW-BTC",
        trade_coin="BTC",
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

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]

    assert review["external_context_summary"]["sample_count"] == 2
    assert review["external_context_summary"]["onchain_state_counts"] == {"bullish": 1, "bearish": 1}
    assert review["external_context_summary"]["etf_state_counts"] == {"inflow": 1, "outflow": 1}
    assert review["external_context_summary"]["avg_learning_weight"] == 1.0
    assert proposal["external_context_summary"] == review["external_context_summary"]
