from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SettingsError(RuntimeError):
    """Raised when runtime settings violate project constraints."""


class SettingsModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = Field(default="upbit-auto-trader")
    trading_mode: str = Field(default="demo")
    learning_enabled: bool = Field(default=True)
    trade_market: str = Field(default="KRW-XRP")
    trade_coin: str = Field(default="XRP")
    upbit_access_key: str = Field(default="")
    upbit_secret_key: str = Field(default="")
    upbit_base_url: str = Field(default="https://api.upbit.com")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    learning_log_dir: Path = Field(default=Path("./logs/learning"))

    @field_validator("trading_mode")
    @classmethod
    def validate_trading_mode(cls, value: str) -> str:
        if value not in {"demo", "live"}:
            raise ValueError("TRADING_MODE must be one of: demo, live")
        return value

    @field_validator("learning_enabled")
    @classmethod
    def validate_learning_enabled(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("LEARNING_ENABLED must remain true in every mode")
        return value

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        if value != "json":
            raise ValueError("LOG_FORMAT must be json")
        return value


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    trading_mode: str
    learning_enabled: bool
    trade_market: str
    trade_coin: str
    upbit_access_key: str
    upbit_secret_key: str
    upbit_base_url: str
    log_level: str
    log_format: str
    learning_log_dir: Path


def load_settings() -> AppSettings:
    payload = {
        "app_name": os.getenv("APP_NAME", "upbit-auto-trader"),
        "trading_mode": os.getenv("TRADING_MODE", "demo"),
        "learning_enabled": _parse_bool(os.getenv("LEARNING_ENABLED", "true")),
        "trade_market": os.getenv("TRADE_MARKET", "KRW-XRP"),
        "trade_coin": os.getenv("TRADE_COIN", "XRP"),
        "upbit_access_key": os.getenv("UPBIT_ACCESS_KEY", ""),
        "upbit_secret_key": os.getenv("UPBIT_SECRET_KEY", ""),
        "upbit_base_url": os.getenv("UPBIT_BASE_URL", "https://api.upbit.com"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_format": os.getenv("LOG_FORMAT", "json"),
        "learning_log_dir": Path(os.getenv("LEARNING_LOG_DIR", "./logs/learning")),
    }

    try:
        validated = SettingsModel.model_validate(payload)
    except ValidationError as exc:
        raise SettingsError(str(exc)) from exc

    return AppSettings(
        app_name=validated.app_name,
        trading_mode=validated.trading_mode,
        learning_enabled=validated.learning_enabled,
        trade_market=validated.trade_market,
        trade_coin=validated.trade_coin,
        upbit_access_key=validated.upbit_access_key,
        upbit_secret_key=validated.upbit_secret_key,
        upbit_base_url=validated.upbit_base_url,
        log_level=validated.log_level,
        log_format=validated.log_format,
        learning_log_dir=validated.learning_log_dir,
    )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError("LEARNING_ENABLED must be a boolean-compatible value")
