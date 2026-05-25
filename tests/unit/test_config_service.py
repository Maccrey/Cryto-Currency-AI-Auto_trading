from pathlib import Path

import pytest

from app.services.config.env_file import EnvFileService


def test_env_file_service_saves_settings_and_masks_secret_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "live",
            "LEARNING_ENABLED": "true",
            "TRADE_MARKET": "KRW-XRP",
            "TRADE_COIN": "XRP",
            "UPBIT_ACCESS_KEY": "access-key",
            "UPBIT_SECRET_KEY": "secret-key",
        },
    )

    assert result["status"] == "saved"
    assert "UPBIT_ACCESS_KEY=access-key" in env_path.read_text(encoding="utf-8")
    current = service.current()
    assert current["values"]["TRADING_MODE"] == "live"
    assert current["values"]["UPBIT_ACCESS_KEY"] == "***"
    assert current["missing_for_live"] == []


def test_env_file_service_exposes_sideways_risk_defaults(tmp_path: Path) -> None:
    service = EnvFileService(tmp_path / ".env")

    current = service.current()

    assert current["values"]["SIDEWAYS_RISK_GUARD_ENABLED"] == "true"
    assert current["values"]["SIDEWAYS_PRICE_RANGE_PCT"] == "0.002"
    assert current["values"]["SIDEWAYS_TRADED_VALUE_RANGE_PCT"] == "0.003"
    assert current["values"]["SIDEWAYS_MAX_AVG_ABS_RETURN_PCT"] == "0.001"
    assert current["values"]["SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT"] == "0.003"


def test_env_file_service_uses_machine_name_when_server_name_is_blank(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("app.services.config.env_file.socket.gethostname", lambda: "seoul-demo.local")
    env_path = tmp_path / ".env"
    service = EnvFileService(env_path)

    current = service.current()
    result = service.save(
        {
            "TRADING_MODE": "demo",
            "LEARNING_ENABLED": "true",
            "SERVER_NAME": "",
        },
    )

    assert current["values"]["SERVER_NAME"] == "seoul-demo"
    assert result["saved"] is True
    assert "SERVER_NAME=seoul-demo" in env_path.read_text(encoding="utf-8")


def test_env_file_service_server_name_prefers_saved_value_over_runtime_fallback(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("SERVER_NAME=서울-데모-저장값\n", encoding="utf-8")
    service = EnvFileService(env_path)

    assert service.server_name(fallback="초기환경값") == "서울-데모-저장값"


def test_env_file_service_demo_initial_capital_prefers_saved_positive_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DEMO_INITIAL_CAPITAL=2500000\n", encoding="utf-8")
    service = EnvFileService(env_path)

    assert service.demo_initial_capital(fallback=1_000_000) == 2_500_000


def test_env_file_service_demo_initial_capital_falls_back_when_invalid(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DEMO_INITIAL_CAPITAL=0\n", encoding="utf-8")
    service = EnvFileService(env_path)

    assert service.demo_initial_capital(fallback=1_000_000) == 1_000_000


def test_env_file_service_reports_missing_keys_when_switching_to_live(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TRADING_MODE=live\nLEARNING_ENABLED=true\n", encoding="utf-8")
    service = EnvFileService(env_path)

    current = service.current()

    assert current["mode"] == "live"
    assert current["missing_for_live"] == ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]


def test_env_file_service_keeps_existing_secret_when_form_submits_blank_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TRADING_MODE=demo\nLEARNING_ENABLED=true\nUPBIT_ACCESS_KEY=old-access\nUPBIT_SECRET_KEY=old-secret\n",
        encoding="utf-8",
    )
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "live",
            "LEARNING_ENABLED": "true",
            "UPBIT_ACCESS_KEY": "",
            "UPBIT_SECRET_KEY": "",
        },
    )

    assert result["saved"] is True
    env_text = env_path.read_text(encoding="utf-8")
    assert "UPBIT_ACCESS_KEY=old-access" in env_text
    assert "UPBIT_SECRET_KEY=old-secret" in env_text


def test_env_file_service_keeps_existing_secret_when_form_submits_mask(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TRADING_MODE=demo\nLEARNING_ENABLED=true\nTELEGRAM_BOT_TOKEN=old-token\n",
        encoding="utf-8",
    )
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "demo",
            "LEARNING_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "********",
        },
    )

    assert result["saved"] is True
    assert "TELEGRAM_BOT_TOKEN=old-token" in env_path.read_text(encoding="utf-8")
    assert service.current()["values"]["TELEGRAM_BOT_TOKEN"] == "***"


def test_env_file_service_reveals_supported_secret_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TRADING_MODE=demo\nLEARNING_ENABLED=true\nTELEGRAM_BOT_TOKEN=old-token\n",
        encoding="utf-8",
    )
    service = EnvFileService(env_path)

    result = service.secret_value("TELEGRAM_BOT_TOKEN")

    assert result == {
        "status": "ok",
        "found": True,
        "key": "TELEGRAM_BOT_TOKEN",
        "value": "old-token",
    }


def test_env_file_service_rejects_unsupported_secret_value(tmp_path: Path) -> None:
    service = EnvFileService(tmp_path / ".env")

    result = service.secret_value("UNKNOWN_SECRET")

    assert result["status"] == "invalid"
    assert result["found"] is False
    assert result["value"] == ""


def test_env_file_service_normalizes_telegram_group_chat_identity(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "demo",
            "LEARNING_ENABLED": "true",
            "TELEGRAM_CHAT_ID": "telegram:group:-1003988291151",
            "TELEGRAM_USER_ID": "467359360",
            "TELEGRAM_USERNAME": "@maccrey",
            "TELEGRAM_ALLOW_FROM": "467359360",
        },
    )

    assert result["saved"] is True
    env_text = env_path.read_text(encoding="utf-8")
    assert "TELEGRAM_CHAT_ID=-1003988291151" in env_text
    assert "TELEGRAM_USER_ID=467359360" in env_text
    assert "TELEGRAM_USERNAME=@maccrey" in env_text
    assert "TELEGRAM_ALLOW_FROM=467359360" in env_text


def test_env_file_service_saves_trading_profile_defaults(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "demo",
            "LEARNING_ENABLED": "true",
            "TRADING_PROFILE": "long_term",
        },
    )

    assert result["saved"] is True
    assert result["profile"] == "long_term"
    env_text = env_path.read_text(encoding="utf-8")
    assert "TRADING_PROFILE=long_term" in env_text
    assert "AUTO_TRADING_INTERVAL_SEC=60.0" in env_text
    assert "AUTO_TRADING_MIN_HISTORY=30" in env_text
    assert "PROFILE_MIN_NET_EDGE_PCT=0.012" in env_text
    assert "STOP_LOSS_WEAK=0.1" in env_text
    assert "STOP_LOSS_MEDIUM=0.1" in env_text
    assert "STOP_LOSS_STRONG=0.1" in env_text
    assert "STOP_LOSS_VERY_STRONG=0.1" in env_text
    current = service.current()
    assert {profile["key"] for profile in current["profiles"]} == {
        "scalping",
        "short_term",
        "mid_term",
        "long_term",
    }
    long_term = next(profile for profile in current["profiles"] if profile["key"] == "long_term")
    assert long_term["fixed_stop_loss_pct"] == 0.1


def test_env_file_service_updates_market_when_coin_changes_from_default_xrp(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TRADING_MODE=demo\nLEARNING_ENABLED=true\nTRADE_MARKET=KRW-XRP\nTRADE_COIN=XRP\n",
        encoding="utf-8",
    )
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "demo",
            "TRADING_PROFILE": "scalping",
            "TRADE_COIN": "btc",
            "DEMO_INITIAL_CAPITAL": "1000000",
        },
    )

    assert result["saved"] is True
    env_text = env_path.read_text(encoding="utf-8")
    assert "TRADE_COIN=BTC" in env_text
    assert "TRADE_MARKET=KRW-BTC" in env_text


def test_env_file_service_normalizes_krw_market_to_trade_coin(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    service = EnvFileService(env_path)

    result = service.save(
        {
            "TRADING_MODE": "demo",
            "TRADING_PROFILE": "scalping",
            "TRADE_MARKET": "KRW-ETH",
            "TRADE_COIN": "btc",
            "DEMO_INITIAL_CAPITAL": "1000000",
        },
    )

    assert result["saved"] is True
    env_text = env_path.read_text(encoding="utf-8")
    assert "TRADE_COIN=BTC" in env_text
    assert "TRADE_MARKET=KRW-BTC" in env_text


def test_env_file_service_readiness_blocks_market_coin_mismatch(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "TRADING_MODE=demo",
                "TRADING_PROFILE=scalping",
                "TRADE_MARKET=KRW-ETH",
                "TRADE_COIN=BTC",
                "DEMO_INITIAL_CAPITAL=1000000",
            ],
        ),
        encoding="utf-8",
    )
    service = EnvFileService(env_path)

    readiness = service.trading_start_readiness()

    assert readiness["ready"] is False
    assert "TRADE_MARKET" in readiness["invalid"]
