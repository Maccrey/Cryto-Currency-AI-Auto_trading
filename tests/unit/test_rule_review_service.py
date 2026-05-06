from pathlib import Path
import json

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


def test_rule_proposal_allows_demo_no_trade_mitigation_with_small_trade_sample(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                (
                    '{"event_name":"auto_trade_cycle","payload":'
                    '{"status":"blocked","reason":"AUTO_MIN_SIGNAL_LEVEL",'
                    '"sizing_blocked_reason":"FEE_ADJUSTED_EDGE_LIMIT"}}'
                ),
                (
                    '{"event_name":"auto_trade_cycle","payload":'
                    '{"status":"blocked","reason":"AUTO_MIN_SIGNAL_LEVEL",'
                    '"sizing_blocked_reason":"FEE_ADJUSTED_EDGE_LIMIT"}}'
                ),
                (
                    '{"event_name":"auto_trade_cycle","payload":'
                    '{"status":"blocked","reason":"AUTO_MIN_SIGNAL_LEVEL",'
                    '"sizing_blocked_reason":"FEE_ADJUSTED_EDGE_LIMIT"}}'
                ),
            ],
        )
        + "\n",
        encoding="utf-8",
    )
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

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]
    initial_status = proposal["status"]
    initial_rejection_reasons = list(proposal["rejection_reasons"])
    initial_parameters = [change["parameter"] for change in proposal["codex_suggested_changes"]]
    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    result = service.apply_demo(str(proposal["id"]))["proposal"]

    assert review["trade_count"] == 0
    assert review["stop_loss_count"] == 0
    assert review["no_trade_blocked_count"] == 6
    assert initial_status == "proposed"
    assert initial_rejection_reasons == []
    assert initial_parameters == [
        "NO_TRADE_RELAX_MIN_SCORE",
        "DEMO_FEE_EDGE_RELAXATION",
    ]
    assert result["demo_applied"] is True
    assert result["status"] == "demo_applied"


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
            {"parameter": "BUY_RATIO_STRONG", "proposed_value": 0.30},
        ],
    )

    assert proposal["proposal"]["status"] == "blocked"
    assert "too_many_parameter_changes" in proposal["proposal"]["rejection_reasons"]
    assert len(proposal["proposal"]["codex_suggested_changes"]) == 1


def test_rule_proposal_rejects_stop_loss_parameter_changes(tmp_path: Path) -> None:
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

    proposal = service.create_proposal(
        proposed_changes=[
            {"parameter": "STOP_LOSS_STRONG", "current_value": 0.03, "proposed_value": 0.025},
            {"parameter": "BUY_RATIO_MEDIUM", "current_value": 0.18, "proposed_value": 0.16},
        ],
    )["proposal"]

    assert proposal["status"] == "blocked"
    assert "fixed_stop_loss_locked" in proposal["rejection_reasons"]
    assert proposal["locked_parameters"] == ["STOP_LOSS_STRONG"]
    assert proposal["codex_suggested_changes"] == [
        {"parameter": "BUY_RATIO_MEDIUM", "current_value": 0.18, "proposed_value": 0.16},
    ]


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


def test_rule_change_history_is_appended_for_proposal_lifecycle(tmp_path: Path) -> None:
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
    proposal = service.create_proposal(
        review_id=str(review["id"]),
        proposed_changes=[
            {
                "parameter": "BUY_RATIO_MEDIUM",
                "current_value": 0.18,
                "proposed_value": 0.16,
                "reason": "AUTO_MIN_SIGNAL_LEVEL 차단 반복",
            },
        ],
    )["proposal"]
    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    service.apply_demo(str(proposal["id"]))
    service.approve_live(str(proposal["id"]), approved_by="operator")

    history_path = tmp_path / "rule-change-history.jsonl"
    rows = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]

    assert [row["event_type"] for row in rows] == ["proposal_created", "replay_verified", "demo_applied", "live_approved"]
    assert rows[0]["proposal_id"] == proposal["id"]
    assert rows[0]["trade_coin"] == "BTC"
    assert rows[0]["changed_parameters"] == ["BUY_RATIO_MEDIUM"]
    assert rows[0]["change_reason"] == "AUTO_MIN_SIGNAL_LEVEL 차단 반복"
    assert rows[0]["expected_effect"]
    assert rows[0]["known_risks"]
    assert service.list_history()["count"] == 4


def test_live_approval_is_blocked_when_rule_change_history_is_missing(tmp_path: Path) -> None:
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

    proposal = service.create_proposal()["proposal"]
    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    service.apply_demo(str(proposal["id"]))
    (tmp_path / "rule-change-history.jsonl").unlink()

    result = service.approve_live(str(proposal["id"]), approved_by="operator")

    assert result["proposal"]["live_approved"] is False
    assert "rule_change_history_required" in result["proposal"]["rejection_reasons"]


def test_rule_proposal_warns_when_same_parameter_failed_in_history(tmp_path: Path) -> None:
    history_path = tmp_path / "rule-change-history.jsonl"
    history_path.write_text(
        json.dumps(
            {
                "event_type": "live_approval_rejected",
                "proposal_id": "old-proposal",
                "changed_parameters": ["BUY_RATIO_MEDIUM"],
                "approval_status": "rejected",
                "blocked_reason_summary": ["demo_apply_required"],
                "created_at": "2026-05-01T00:00:00+00:00",
            },
        )
        + "\n",
        encoding="utf-8",
    )
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

    proposal = service.create_proposal(
        proposed_changes=[
            {
                "parameter": "BUY_RATIO_MEDIUM",
                "current_value": 0.18,
                "proposed_value": 0.16,
                "reason": "신호 차단 완화",
            },
        ],
    )["proposal"]

    assert proposal["history_warnings"] == [
        {
            "parameter": "BUY_RATIO_MEDIUM",
            "previous_proposal_id": "old-proposal",
            "previous_event_type": "live_approval_rejected",
            "previous_approval_status": "rejected",
            "previous_blocked_reasons": ["demo_apply_required"],
            "message": "BUY_RATIO_MEDIUM 파라미터는 과거 실패/거절 이력이 있습니다.",
        },
    ]


def test_rule_change_history_links_commit_hash_as_append_only_event(tmp_path: Path) -> None:
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

    proposal = service.create_proposal(
        proposed_changes=[
            {
                "parameter": "BUY_RATIO_MEDIUM",
                "current_value": 0.18,
                "proposed_value": 0.16,
                "reason": "BTC 무거래 완화",
            },
        ],
    )["proposal"]

    result = service.attach_commit_hash(str(proposal["id"]), commit_hash="abc1234")

    assert result["proposal"]["commit_hash"] == "abc1234"
    history_path = tmp_path / "rule-change-history.jsonl"
    rows = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert [row["event_type"] for row in rows] == ["proposal_created", "commit_linked"]
    assert rows[0]["commit_hash"] == ""
    assert rows[1]["proposal_id"] == proposal["id"]
    assert rows[1]["commit_hash"] == "abc1234"
    assert rows[1]["approval_status"] == "linked"
    assert service.list_history()["history"][0]["event_type"] == "commit_linked"


def test_rule_change_history_correction_is_append_only(tmp_path: Path) -> None:
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
    proposal = service.create_proposal()["proposal"]

    result = service.append_history_correction(
        str(proposal["id"]),
        reason="커밋 해시 설명 누락 보정",
        corrected_fields={"commit_hash": "abc1234"},
        corrected_by="operator",
    )

    rows = [json.loads(line) for line in (tmp_path / "rule-change-history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result["correction"] == {
        "reason": "커밋 해시 설명 누락 보정",
        "corrected_fields": {"commit_hash": "abc1234"},
        "corrected_by": "operator",
    }
    assert [row["event_type"] for row in rows] == ["proposal_created", "correction"]
    assert rows[1]["approval_status"] == "corrected"
    assert rows[1]["change_reason"] == "커밋 해시 설명 누락 보정"
    assert rows[1]["correction_detail"]["corrected_fields"] == {"commit_hash": "abc1234"}


def test_rule_change_rollback_updates_proposal_and_appends_history(tmp_path: Path) -> None:
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
    proposal = service.create_proposal()["proposal"]
    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    service.apply_demo(str(proposal["id"]))

    result = service.rollback_proposal(
        str(proposal["id"]),
        reason="demo 손절률 악화로 되돌림",
        target="demo",
        rolled_back_by="operator",
    )

    rows = [json.loads(line) for line in (tmp_path / "rule-change-history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result["proposal"]["status"] == "rolled_back"
    assert result["proposal"]["demo_applied"] is False
    assert result["rollback"] == {
        "reason": "demo 손절률 악화로 되돌림",
        "target": "demo",
        "rolled_back_by": "operator",
    }
    assert [row["event_type"] for row in rows] == ["proposal_created", "replay_verified", "demo_applied", "rollback"]
    assert rows[-1]["approval_status"] == "rolled_back"
    assert rows[-1]["change_reason"] == "demo 손절률 악화로 되돌림"
    assert rows[-1]["rollback_detail"]["target"] == "demo"
