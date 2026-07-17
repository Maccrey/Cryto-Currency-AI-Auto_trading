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
        "BULL_BOX_BEAR_REBOUND_SIGNAL_BOOST",
        "BROAD_MARKET_STATE_CLASSIFIER",
    ]
    assert result["demo_applied"] is True
    assert result["status"] == "demo_applied"


def test_auto_improve_notifies_telegram_when_demo_rule_is_applied(tmp_path: Path) -> None:
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
    gateway = StubTelegramGateway()
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
        telegram_gateway=gateway,
    )

    result = service.auto_improve(fixture_path=Path("fixtures/replay_ticks.json"), force=True)

    assert result["status"] == "completed"
    assert gateway.messages
    assert "자동 룰 개선이 적용되었습니다." in gateway.messages[0]
    markdown = tmp_path / "rule-improvement-learning.md"
    assert markdown.exists()
    markdown_text = markdown.read_text(encoding="utf-8")
    assert "룰 개선 학습 기록" in markdown_text


def test_auto_improve_notifies_telegram_when_replay_is_rejected(tmp_path: Path) -> None:
    gateway = StubTelegramGateway()
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
        telegram_gateway=gateway,
    )

    service.auto_improve(fixture_path=Path("fixtures/replay_ticks.json"), force=True)

    assert gateway.messages
    assert "자동 룰 개선이 보류되었습니다." in gateway.messages[0]


def test_demo_rule_apply_callback_receives_verified_changes(tmp_path: Path) -> None:
    calls: list[list[dict[str, object]]] = []
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
            require_manual_approval=False,
        ),
        demo_rule_apply_callback=lambda changes: calls.append(changes) or {"applied": True},
    )
    proposal = service.create_proposal(
        proposed_changes=[
            {
                "parameter": "NO_TRADE_RELAX_MIN_SCORE",
                "proposed_value": 0.18,
                "reason": "demo test",
            }
        ]
    )["proposal"]

    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    applied = service.apply_demo(str(proposal["id"]))["proposal"]

    assert applied["demo_applied"] is True
    assert calls and calls[0][0]["parameter"] == "NO_TRADE_RELAX_MIN_SCORE"
    assert applied["runtime_rule_update"] == {"applied": True}


def test_rule_review_uses_shadow_variant_results_in_codex_prompt_and_changes(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_name": "auto_trade_cycle",
                        "payload": {
                            "learning_completion_rate": 1.0,
                            "rule_variant_shadow": {
                                "leader_key": "B",
                                "leader_label": "룰 B 추세형",
                                "results": [
                                    {
                                        "variant_key": "A",
                                        "variant_label": "룰 A 안정형",
                                        "profit_rate": 0.001,
                                        "realized_pnl": 100.0,
                                        "promotion_eligible": False,
                                    },
                                    {
                                        "variant_key": "B",
                                        "variant_label": "룰 B 추세형",
                                        "profit_rate": 0.004,
                                        "realized_pnl": 400.0,
                                        "promotion_eligible": True,
                                    },
                                    {
                                        "variant_key": "C",
                                        "variant_label": "룰 C 방어형",
                                        "profit_rate": -0.001,
                                        "realized_pnl": -100.0,
                                        "promotion_eligible": False,
                                    },
                                ],
                            },
                        },
                    },
                    ensure_ascii=True,
                )
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
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]

    assert review["rule_variant_shadow_summary"]["best_variant_key"] == "B"
    assert review["rule_variant_shadow_summary"]["best_positive_variant_key"] == "B"
    assert "A-R 18개 룰 동시 테스트" in review["codex_rule_prompt"]
    assert proposal["codex_suggested_changes"][0]["parameter"] == "TREND_MARKET_SIZE_MULTIPLIER"


def test_rule_review_uses_technical_indicators_in_codex_prompt_and_changes(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_name": "signal_generated",
                        "payload": {
                            "technical_indicators": {
                                "rsi_14": 63.0,
                                "macd_histogram": 0.004,
                                "bollinger_position": 0.62,
                                "ma_trend": 0.012,
                                "stochastic_k": 58.0,
                                "price_position_20": 0.42,
                                "drawdown_from_high_20": -0.012,
                                "rebound_from_low_20": 0.006,
                                "trend_efficiency_20": 0.22,
                            },
                        },
                    },
                    ensure_ascii=True,
                ),
                json.dumps(
                    {
                        "event_name": "signal_generated",
                        "payload": {
                            "technical_indicators": {
                                "rsi_14": 66.0,
                                "macd_histogram": 0.003,
                                "bollinger_position": 0.68,
                                "ma_trend": 0.011,
                                "stochastic_k": 61.0,
                                "price_position_20": 0.55,
                                "drawdown_from_high_20": -0.01,
                                "rebound_from_low_20": 0.008,
                                "trend_efficiency_20": 0.25,
                            },
                        },
                    },
                    ensure_ascii=True,
                ),
                json.dumps(
                    {
                        "event_name": "signal_generated",
                        "payload": {
                            "technical_indicators": {
                                "rsi_14": 69.0,
                                "macd_histogram": 0.002,
                                "bollinger_position": 0.71,
                                "ma_trend": 0.009,
                                "stochastic_k": 65.0,
                                "price_position_20": 0.94,
                                "drawdown_from_high_20": -0.002,
                                "rebound_from_low_20": 0.004,
                                "trend_efficiency_20": 0.2,
                            },
                        },
                    },
                    ensure_ascii=True,
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
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]

    assert review["technical_indicator_summary"]["bullish_momentum_count"] == 3
    assert review["technical_indicator_summary"]["low_rebound_confirmation_count"] == 3
    assert review["technical_indicator_summary"]["high_position_reversal_risk_count"] == 1
    assert "전문 보조지표" in review["codex_rule_prompt"]
    assert proposal["technical_indicator_summary"]["sample_count"] == 3
    assert proposal["codex_suggested_changes"][0]["parameter"] == "TECHNICAL_TREND_CONFIRMATION"


def test_rule_review_summarizes_market_features_and_raw_observations(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_name": "signal_generated",
                        "payload": {
                            "market_features": {
                                "traded_value_multiple": 1.6,
                                "orderbook_imbalance": 0.24,
                                "spread_bps": 8.0,
                                "short_volatility": 0.001,
                            },
                        },
                    },
                    ensure_ascii=True,
                ),
                json.dumps(
                    {
                        "event_name": "auto_trade_cycle",
                        "payload": {
                            "market_window": {
                                "price_change_pct": 0.003,
                                "traded_value_multiple": 1.4,
                            },
                        },
                    },
                    ensure_ascii=True,
                ),
            ],
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "market-observations.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "recorded_at": f"2026-05-22T09:00:0{index}+09:00",
                    "trade_price": 800 + index,
                    "traded_value": 1000000 + index,
                    "spread_bps": 8.0,
                    "orderbook_imbalance": 0.2,
                    "liquidity_score": 0.9,
                    "regime_score": 0.7,
                },
                ensure_ascii=True,
            )
            for index in range(4)
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

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]
    replay = service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))

    assert review["market_data_quality_summary"]["feature_sample_count"] == 1
    assert review["market_data_quality_summary"]["window_sample_count"] == 1
    assert review["market_data_quality_summary"]["raw_observation_count"] == 4
    assert "가격/거래량 데이터 품질" in review["codex_rule_prompt"]
    assert replay["proposal"]["replay_result"]["source"] == "market_observations"


def test_auto_rule_update_skips_when_learning_incomplete_or_win_rate_high(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                '{"event_name":"auto_trade_cycle","payload":{"learning_completion_rate":0.75}}',
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":1000}}',
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":900}}',
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
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
            auto_update_enabled=True,
            auto_update_min_learning_completion_rate=1.0,
            auto_update_win_rate_skip_threshold=0.80,
        ),
    )

    incomplete = service.auto_improve(fixture_path=Path("fixtures/replay_ticks.json"))
    assert incomplete["status"] == "blocked"
    assert "learning_completion_incomplete" in incomplete["proposal"]["rejection_reasons"]

    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                '{"event_name":"auto_trade_cycle","payload":{"learning_completion_rate":1.0}}',
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":1000}}',
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":900}}',
            ],
        )
        + "\n",
        encoding="utf-8",
    )
    high_win_rate = service.auto_improve(fixture_path=Path("fixtures/replay_ticks.json"))

    assert high_win_rate["status"] == "blocked"
    assert high_win_rate["review"]["win_rate"] == 1.0
    assert "win_rate_above_auto_update_threshold" in high_win_rate["proposal"]["rejection_reasons"]


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


def test_demo_apply_is_blocked_when_all_shadow_rules_are_negative(tmp_path: Path) -> None:
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
    proposal["rule_variant_shadow_summary"] = {
        "sample_count": 100,
        "best_variant_key": "B",
        "best_positive_variant_key": None,
        "latest_results": [
            {"variant_key": "B", "profit_rate": -0.001, "realized_pnl": -100.0},
        ],
    }

    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))
    result = service.apply_demo(str(proposal["id"]))["proposal"]

    assert result["demo_applied"] is False
    assert "shadow_no_positive_variant" in result["rejection_reasons"]


def test_demo_apply_resets_shadow_results_after_positive_validation(tmp_path: Path) -> None:
    reset_calls: list[bool] = []
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
        demo_rule_reset_callback=lambda: reset_calls.append(True),
    )
    proposal = service.create_proposal()["proposal"]
    service.verify_replay(str(proposal["id"]), fixture_path=Path("fixtures/replay_ticks.json"))

    result = service.apply_demo(str(proposal["id"]))["proposal"]

    assert result["demo_applied"] is True
    assert result["rule_variant_shadow_reset"] is True
    assert reset_calls == [True]


def test_rule_review_counts_completed_exits_without_fill_or_lifecycle_duplicates(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":100,"is_stop_loss":false}}',
                '{"event_name":"position_exit_completed","payload":{"reason_code":"TAKE_PROFIT","is_stop_loss":false}}',
                '{"event_name":"fill_result","payload":{"side":"sell","pnl":-80,"is_stop_loss":true}}',
                '{"event_name":"position_lifecycle_updated","payload":{"is_stop_loss":true}}',
                '{"event_name":"position_exit_completed","payload":{"reason_code":"STOP_LOSS_MOMENTUM_REVERSAL","is_stop_loss":true}}',
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
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()["review"]

    assert review["trade_count"] == 2
    assert review["stop_loss_count"] == 1
    assert review["win_rate"] == 0.5


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



def test_rule_review_summarizes_24h_trade_staleness_and_prefers_bull_recovery(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_name": "fill_result", "payload": {"side": "buy"}, "recorded_at": "2026-05-01T00:00:00+00:00"}),
                json.dumps(
                    {
                        "event_name": "auto_trade_cycle",
                        "payload": {
                            "status": "blocked",
                            "reason": "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK",
                            "sizing_blocked_reason": "FEE_ADJUSTED_EDGE_LIMIT",
                            "rule_variant_shadow": {
                                "leader_key": "B",
                                "leader_label": "룰 B 추세형",
                                "results": [
                                    {"variant_key": "A", "variant_label": "룰 A 안정형", "profit_rate": 0.0},
                                    {"variant_key": "B", "variant_label": "룰 B 추세형", "profit_rate": 0.004},
                                ],
                            },
                        },
                        "recorded_at": "2026-05-02T02:00:00+00:00",
                    },
                    ensure_ascii=True,
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
            min_trades=0,
            min_stoplosses=0,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )

    review = service.review()["review"]
    proposal = service.create_proposal(review_id=str(review["id"]))["proposal"]

    assert review["trade_staleness_summary"]["no_trade_24h"] is True
    assert review["trade_staleness_summary"]["hours_since_last_trade"] == 26.0
    assert "거래 공백" in review["codex_rule_prompt"]
    assert proposal["codex_suggested_changes"][0]["parameter"] == "BULL_TREND_WEAK_SIGNAL_RECOVERY"

def test_rule_review_summarizes_external_market_context(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        "\n".join(
            [
                '{"event_name":"auto_trade_cycle","payload":{"external_context":{"onchain":{"state":"bullish","exchange_netflow_state":"outflow"},"etf":{"state":"inflow","flow_usd":125000000,"inflow_usd":125000000,"outflow_usd":0},"learning_weight":1.2}}}',
                '{"event_name":"external_market_context_snapshot","payload":{"onchain":{"state":"bearish","exchange_netflow_state":"inflow"},"etf":{"state":"outflow","flow_usd":-50000000,"inflow_usd":0,"outflow_usd":50000000},"learning_weight":0.8}}',
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
    assert review["external_context_summary"]["onchain_exchange_netflow_counts"] == {"outflow": 1, "inflow": 1}
    assert review["external_context_summary"]["etf_state_counts"] == {"inflow": 1, "outflow": 1}
    assert review["external_context_summary"]["avg_learning_weight"] == 1.0
    assert review["external_context_summary"]["etf_flow_usd_total"] == 75_000_000
    assert review["external_context_summary"]["etf_inflow_usd_total"] == 125_000_000
    assert review["external_context_summary"]["etf_outflow_usd_total"] == 50_000_000
    assert proposal["external_context_summary"] == review["external_context_summary"]


def test_rule_proposal_uses_external_context_for_rule_changes(tmp_path: Path) -> None:
    (tmp_path / "learning.jsonl").write_text(
        (
            '{"event_name":"external_market_context_snapshot","payload":'
            '{"onchain":{"state":"bullish","exchange_netflow_state":"outflow"},'
            '"etf":{"state":"inflow","flow_usd":125000000,"inflow_usd":125000000,"outflow_usd":0},'
            '"learning_weight":1.16}}\n'
        ),
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

    proposal = service.create_proposal()["proposal"]
    parameters = [change["parameter"] for change in proposal["codex_suggested_changes"]]

    assert "EXTERNAL_CONTEXT_BULLISH_BOOST" in parameters
    assert "EXTERNAL_CONTEXT_POSITION_SCALING" in parameters


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
    assert rows[0]["optimization_tracking"]["changed_parameters"] == ["BUY_RATIO_MEDIUM"]
    assert "no_trade_blocked_count_delta" in rows[0]["optimization_tracking"]["post_update_metrics_to_compare"]
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
class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)
