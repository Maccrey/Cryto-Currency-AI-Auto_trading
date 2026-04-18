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

    settings = load_settings()

    assert settings.trading_mode == "live"
    assert settings.learning_enabled is True

