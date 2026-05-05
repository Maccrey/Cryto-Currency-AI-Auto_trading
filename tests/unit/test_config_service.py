from pathlib import Path

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
    current = service.current()
    assert {profile["key"] for profile in current["profiles"]} == {
        "scalping",
        "short_term",
        "mid_term",
        "long_term",
    }


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
