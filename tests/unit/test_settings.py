from pathlib import Path

import pytest

from app.core.settings import SettingsError, load_settings


def test_invalid_trading_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    with pytest.raises(SettingsError, match="TRADING_MODE"):
        load_settings()


def test_learning_disabled_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "false")

    with pytest.raises(SettingsError, match="LEARNING_ENABLED"):
        load_settings()


def test_valid_settings_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("DASHBOARD_PORT", "9090")
    monkeypatch.setenv("TRADING_FEE_RATE", "0.0005")
    monkeypatch.setenv("PROFILE_MIN_NET_EDGE_PCT", "0.0008")

    settings = load_settings()

    assert settings.trading_mode == "live"
    assert settings.learning_enabled is True
    assert settings.dashboard_port == 9090
    assert settings.trading_profile == "scalping"
    assert settings.trading_fee_rate == 0.0005
    assert settings.min_order_amount_krw == 5000
    assert settings.profile_min_net_edge_pct == 0.0008
    assert settings.auto_trading_interval_sec == 3.0
    assert settings.rule_review_enabled is True
    assert settings.rule_review_window_days == 14
    assert settings.rule_review_min_trades == 100
    assert settings.rule_review_min_stoplosses == 20
    assert settings.rule_change_max_params_per_run == 3
    assert settings.rule_change_apply_target == "demo"
    assert settings.rule_change_require_manual_approval is True
    assert settings.external_context_enabled is True
    assert settings.onchain_context_source == "manual"
    assert settings.onchain_context_url == ""
    assert settings.etf_context_source == "manual"
    assert settings.etf_context_url == ""
    assert settings.no_trade_adaptive_enabled is True
    assert settings.no_trade_relax_after_cycles == 100


def test_rule_change_apply_target_must_be_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("RULE_CHANGE_APPLY_TARGET", "live")

    with pytest.raises(SettingsError, match="RULE_CHANGE_APPLY_TARGET"):
        load_settings()


def test_invalid_scalping_fee_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADING_FEE_RATE", "0.02")

    with pytest.raises(SettingsError, match="TRADING_FEE_RATE"):
        load_settings()


def test_trading_profile_applies_profile_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADING_PROFILE", "mid_term")
    monkeypatch.delenv("AUTO_TRADING_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("AUTO_TRADING_MIN_HISTORY", raising=False)
    monkeypatch.delenv("PROFILE_MIN_NET_EDGE_PCT", raising=False)
    monkeypatch.delenv("SCALPING_MIN_NET_EDGE_PCT", raising=False)

    settings = load_settings(env_file=tmp_path / ".env")

    assert settings.trading_profile == "mid_term"
    assert settings.auto_trading_interval_sec == 30.0
    assert settings.auto_trading_min_history == 20
    assert settings.profile_min_net_edge_pct == 0.0060
    assert settings.validation_window_sec == 3600


def test_settings_loads_values_from_env_file_without_api_keys_in_demo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "TRADING_MODE=demo",
                "LEARNING_ENABLED=true",
                "TRADE_MARKET=KRW-BTC",
                "TRADE_COIN=BTC",
            ],
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("UPBIT_ACCESS_KEY", raising=False)
    monkeypatch.delenv("UPBIT_SECRET_KEY", raising=False)

    settings = load_settings(env_file=env_file)

    assert settings.trading_mode == "demo"
    assert settings.trade_market == "KRW-BTC"
    assert settings.demo_initial_capital == 1_000_000
    assert settings.upbit_access_key == ""
    assert settings.upbit_secret_key == ""


def test_env_spec_variables_are_loaded_by_settings_schema() -> None:
    expected_fields = {
        "app_env",
        "app_name",
        "app_timezone",
        "trading_mode",
        "learning_enabled",
        "rule_review_enabled",
        "rule_review_window_days",
        "rule_review_min_trades",
        "rule_review_min_stoplosses",
        "rule_change_max_params_per_run",
        "rule_change_apply_target",
        "rule_change_require_manual_approval",
        "external_context_enabled",
        "onchain_context_source",
        "onchain_context_url",
        "onchain_state",
        "onchain_active_addresses_change_pct",
        "onchain_exchange_netflow_state",
        "etf_context_source",
        "etf_context_url",
        "etf_state",
        "etf_flow_usd",
        "no_trade_adaptive_enabled",
        "no_trade_relax_after_cycles",
        "no_trade_relax_min_score",
        "trade_market",
        "trade_coin",
        "upbit_access_key",
        "upbit_secret_key",
        "upbit_base_url",
        "upbit_ws_public_url",
        "upbit_ws_private_url",
        "telegram_bot_token",
        "telegram_chat_id",
        "telegram_notify_in_demo",
        "buy_ratio_weak",
        "buy_ratio_medium",
        "buy_ratio_strong",
        "buy_ratio_very_strong",
        "sell_ratio_weak",
        "sell_ratio_medium",
        "sell_ratio_strong",
        "sell_ratio_very_strong",
        "stop_loss_weak",
        "stop_loss_medium",
        "stop_loss_strong",
        "stop_loss_very_strong",
        "validation_window_sec",
        "min_expected_return_pct",
        "trading_profile",
        "trading_fee_rate",
        "min_order_amount_krw",
        "profile_min_net_edge_pct",
        "min_cash_reserve",
        "max_daily_loss",
        "max_slippage_bps",
        "max_spread_bps",
        "cooldown_seconds",
        "reentry_block_seconds",
        "safe_mode_on_restart",
        "restart_notify",
        "restart_hard_stop_threshold",
        "restart_state_path",
        "auto_promote_to_live",
        "promotion_require_manual_approval",
        "demo_min_days",
        "demo_min_trades",
        "demo_min_win_rate",
        "demo_min_profit_factor",
        "demo_max_drawdown",
        "demo_max_stoploss_failures",
        "demo_initial_capital",
        "auto_trading_enabled",
        "auto_trading_live_enabled",
        "auto_trading_interval_sec",
        "auto_trading_min_history",
        "log_level",
        "log_format",
        "learning_log_dir",
        "learning_dataset_dir",
        "model_feature_logging",
        "decision_trace_logging",
        "dashboard_host",
        "dashboard_port",
        "env_file_path",
    }

    settings = load_settings()

    assert expected_fields <= set(settings.__dataclass_fields__)
