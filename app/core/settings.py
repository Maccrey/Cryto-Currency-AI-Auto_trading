from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SettingsError(RuntimeError):
    """Raised when runtime settings violate project constraints."""


class SettingsModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: str = Field(default="production")
    app_name: str = Field(default="upbit-auto-trader")
    app_timezone: str = Field(default="Asia/Seoul")
    trading_mode: str = Field(default="demo")
    learning_enabled: bool = Field(default=True)
    trade_market: str = Field(default="KRW-XRP")
    trade_coin: str = Field(default="XRP")
    upbit_access_key: str = Field(default="")
    upbit_secret_key: str = Field(default="")
    upbit_base_url: str = Field(default="https://api.upbit.com")
    upbit_ws_public_url: str = Field(default="wss://api.upbit.com/websocket/v1")
    upbit_ws_private_url: str = Field(default="wss://api.upbit.com/websocket/v1/private")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    telegram_notify_in_demo: bool = Field(default=True)
    buy_ratio_weak: float = Field(default=0.08)
    buy_ratio_medium: float = Field(default=0.18)
    buy_ratio_strong: float = Field(default=0.35)
    buy_ratio_very_strong: float = Field(default=0.55)
    sell_ratio_weak: float = Field(default=0.12)
    sell_ratio_medium: float = Field(default=0.28)
    sell_ratio_strong: float = Field(default=0.45)
    sell_ratio_very_strong: float = Field(default=0.70)
    stop_loss_weak: float = Field(default=0.008)
    stop_loss_medium: float = Field(default=0.012)
    stop_loss_strong: float = Field(default=0.018)
    stop_loss_very_strong: float = Field(default=0.022)
    validation_window_sec: int = Field(default=180)
    min_expected_return_pct: float = Field(default=0.004)
    min_cash_reserve: int = Field(default=100000)
    max_daily_loss: int = Field(default=150000)
    max_slippage_bps: int = Field(default=20)
    max_spread_bps: int = Field(default=15)
    cooldown_seconds: int = Field(default=60)
    reentry_block_seconds: int = Field(default=180)
    safe_mode_on_restart: bool = Field(default=True)
    restart_notify: bool = Field(default=True)
    restart_hard_stop_threshold: int = Field(default=3)
    auto_promote_to_live: bool = Field(default=False)
    promotion_require_manual_approval: bool = Field(default=True)
    demo_min_days: int = Field(default=14)
    demo_min_trades: int = Field(default=100)
    demo_min_win_rate: float = Field(default=0.52)
    demo_min_profit_factor: float = Field(default=1.20)
    demo_max_drawdown: float = Field(default=0.08)
    demo_max_stoploss_failures: int = Field(default=0)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    learning_log_dir: Path = Field(default=Path("./logs/learning"))
    learning_dataset_dir: Path = Field(default=Path("./data/learning"))
    model_feature_logging: bool = Field(default=True)
    decision_trace_logging: bool = Field(default=True)
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: int = Field(default=8080)

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
    app_env: str
    app_name: str
    app_timezone: str
    trading_mode: str
    learning_enabled: bool
    trade_market: str
    trade_coin: str
    upbit_access_key: str
    upbit_secret_key: str
    upbit_base_url: str
    upbit_ws_public_url: str
    upbit_ws_private_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_notify_in_demo: bool
    buy_ratio_weak: float
    buy_ratio_medium: float
    buy_ratio_strong: float
    buy_ratio_very_strong: float
    sell_ratio_weak: float
    sell_ratio_medium: float
    sell_ratio_strong: float
    sell_ratio_very_strong: float
    stop_loss_weak: float
    stop_loss_medium: float
    stop_loss_strong: float
    stop_loss_very_strong: float
    validation_window_sec: int
    min_expected_return_pct: float
    min_cash_reserve: int
    max_daily_loss: int
    max_slippage_bps: int
    max_spread_bps: int
    cooldown_seconds: int
    reentry_block_seconds: int
    safe_mode_on_restart: bool
    restart_notify: bool
    restart_hard_stop_threshold: int
    auto_promote_to_live: bool
    promotion_require_manual_approval: bool
    demo_min_days: int
    demo_min_trades: int
    demo_min_win_rate: float
    demo_min_profit_factor: float
    demo_max_drawdown: float
    demo_max_stoploss_failures: int
    log_level: str
    log_format: str
    learning_log_dir: Path
    learning_dataset_dir: Path
    model_feature_logging: bool
    decision_trace_logging: bool
    dashboard_host: str
    dashboard_port: int


def load_settings() -> AppSettings:
    payload = {
        "app_env": os.getenv("APP_ENV", "production"),
        "app_name": os.getenv("APP_NAME", "upbit-auto-trader"),
        "app_timezone": os.getenv("APP_TIMEZONE", "Asia/Seoul"),
        "trading_mode": os.getenv("TRADING_MODE", "demo"),
        "learning_enabled": _parse_bool(os.getenv("LEARNING_ENABLED", "true")),
        "trade_market": os.getenv("TRADE_MARKET", "KRW-XRP"),
        "trade_coin": os.getenv("TRADE_COIN", "XRP"),
        "upbit_access_key": os.getenv("UPBIT_ACCESS_KEY", ""),
        "upbit_secret_key": os.getenv("UPBIT_SECRET_KEY", ""),
        "upbit_base_url": os.getenv("UPBIT_BASE_URL", "https://api.upbit.com"),
        "upbit_ws_public_url": os.getenv("UPBIT_WS_PUBLIC_URL", "wss://api.upbit.com/websocket/v1"),
        "upbit_ws_private_url": os.getenv(
            "UPBIT_WS_PRIVATE_URL",
            "wss://api.upbit.com/websocket/v1/private",
        ),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "telegram_notify_in_demo": _parse_bool(os.getenv("TELEGRAM_NOTIFY_IN_DEMO", "true")),
        "buy_ratio_weak": float(os.getenv("BUY_RATIO_WEAK", "0.08")),
        "buy_ratio_medium": float(os.getenv("BUY_RATIO_MEDIUM", "0.18")),
        "buy_ratio_strong": float(os.getenv("BUY_RATIO_STRONG", "0.35")),
        "buy_ratio_very_strong": float(os.getenv("BUY_RATIO_VERY_STRONG", "0.55")),
        "sell_ratio_weak": float(os.getenv("SELL_RATIO_WEAK", "0.12")),
        "sell_ratio_medium": float(os.getenv("SELL_RATIO_MEDIUM", "0.28")),
        "sell_ratio_strong": float(os.getenv("SELL_RATIO_STRONG", "0.45")),
        "sell_ratio_very_strong": float(os.getenv("SELL_RATIO_VERY_STRONG", "0.70")),
        "stop_loss_weak": float(os.getenv("STOP_LOSS_WEAK", "0.008")),
        "stop_loss_medium": float(os.getenv("STOP_LOSS_MEDIUM", "0.012")),
        "stop_loss_strong": float(os.getenv("STOP_LOSS_STRONG", "0.018")),
        "stop_loss_very_strong": float(os.getenv("STOP_LOSS_VERY_STRONG", "0.022")),
        "validation_window_sec": int(os.getenv("VALIDATION_WINDOW_SEC", "180")),
        "min_expected_return_pct": float(os.getenv("MIN_EXPECTED_RETURN_PCT", "0.004")),
        "min_cash_reserve": int(os.getenv("MIN_CASH_RESERVE", "100000")),
        "max_daily_loss": int(os.getenv("MAX_DAILY_LOSS", "150000")),
        "max_slippage_bps": int(os.getenv("MAX_SLIPPAGE_BPS", "20")),
        "max_spread_bps": int(os.getenv("MAX_SPREAD_BPS", "15")),
        "cooldown_seconds": int(os.getenv("COOLDOWN_SECONDS", "60")),
        "reentry_block_seconds": int(os.getenv("REENTRY_BLOCK_SECONDS", "180")),
        "safe_mode_on_restart": _parse_bool(os.getenv("SAFE_MODE_ON_RESTART", "true")),
        "restart_notify": _parse_bool(os.getenv("RESTART_NOTIFY", "true")),
        "restart_hard_stop_threshold": int(os.getenv("RESTART_HARD_STOP_THRESHOLD", "3")),
        "auto_promote_to_live": _parse_bool(os.getenv("AUTO_PROMOTE_TO_LIVE", "false")),
        "promotion_require_manual_approval": _parse_bool(
            os.getenv("PROMOTION_REQUIRE_MANUAL_APPROVAL", "true"),
        ),
        "demo_min_days": int(os.getenv("DEMO_MIN_DAYS", "14")),
        "demo_min_trades": int(os.getenv("DEMO_MIN_TRADES", "100")),
        "demo_min_win_rate": float(os.getenv("DEMO_MIN_WIN_RATE", "0.52")),
        "demo_min_profit_factor": float(os.getenv("DEMO_MIN_PROFIT_FACTOR", "1.20")),
        "demo_max_drawdown": float(os.getenv("DEMO_MAX_DRAWDOWN", "0.08")),
        "demo_max_stoploss_failures": int(os.getenv("DEMO_MAX_STOPLOSS_FAILURES", "0")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "log_format": os.getenv("LOG_FORMAT", "json"),
        "learning_log_dir": Path(os.getenv("LEARNING_LOG_DIR", "./logs/learning")),
        "learning_dataset_dir": Path(os.getenv("LEARNING_DATASET_DIR", "./data/learning")),
        "model_feature_logging": _parse_bool(os.getenv("MODEL_FEATURE_LOGGING", "true")),
        "decision_trace_logging": _parse_bool(os.getenv("DECISION_TRACE_LOGGING", "true")),
        "dashboard_host": os.getenv("DASHBOARD_HOST", "0.0.0.0"),
        "dashboard_port": int(os.getenv("DASHBOARD_PORT", "8080")),
    }

    try:
        validated = SettingsModel.model_validate(payload)
    except ValidationError as exc:
        raise SettingsError(str(exc)) from exc

    return AppSettings(**validated.model_dump())


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError("LEARNING_ENABLED must be a boolean-compatible value")
