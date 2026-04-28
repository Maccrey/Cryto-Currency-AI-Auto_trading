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
