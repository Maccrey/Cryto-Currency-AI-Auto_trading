from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.trading_profile import TRADING_PROFILES, get_trading_profile


class SettingsError(RuntimeError):
    """Raised when runtime settings violate project constraints."""


class SettingsModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: str = Field(default="production")
    app_name: str = Field(default="upbit-auto-trader")
    app_timezone: str = Field(default="Asia/Seoul")
    trading_mode: str = Field(default="demo")
    learning_enabled: bool = Field(default=True)
    rule_review_enabled: bool = Field(default=True)
    rule_review_window_days: int = Field(default=14)
    rule_review_min_trades: int = Field(default=100)
    rule_review_min_stoplosses: int = Field(default=20)
    rule_change_max_params_per_run: int = Field(default=3)
    rule_change_apply_target: str = Field(default="demo")
    rule_change_require_manual_approval: bool = Field(default=True)
    external_context_enabled: bool = Field(default=True)
    onchain_context_source: str = Field(default="manual")
    onchain_context_url: str = Field(default="")
    onchain_state: str = Field(default="neutral")
    onchain_active_addresses_change_pct: float = Field(default=0.0)
    onchain_exchange_netflow_state: str = Field(default="neutral")
    etf_context_source: str = Field(default="manual")
    etf_context_url: str = Field(default="")
    etf_state: str = Field(default="neutral")
    etf_flow_usd: float = Field(default=0.0)
    no_trade_adaptive_enabled: bool = Field(default=True)
    no_trade_relax_after_cycles: int = Field(default=100)
    no_trade_relax_min_score: float = Field(default=0.30)
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
    trading_profile: str = Field(default="scalping")
    trading_fee_rate: float = Field(default=0.0005)
    min_order_amount_krw: float = Field(default=5_000.0)
    profile_min_net_edge_pct: float = Field(default=0.0008)
    min_cash_reserve: int = Field(default=100000)
    max_daily_loss: int = Field(default=150000)
    max_slippage_bps: int = Field(default=20)
    max_spread_bps: int = Field(default=15)
    cooldown_seconds: int = Field(default=60)
    reentry_block_seconds: int = Field(default=180)
    safe_mode_on_restart: bool = Field(default=True)
    restart_notify: bool = Field(default=True)
    restart_hard_stop_threshold: int = Field(default=3)
    restart_state_path: Path = Field(default=Path("./logs/recovery/restart-state.json"))
    auto_promote_to_live: bool = Field(default=False)
    promotion_require_manual_approval: bool = Field(default=True)
    demo_min_days: int = Field(default=14)
    demo_min_trades: int = Field(default=100)
    demo_min_win_rate: float = Field(default=0.52)
    demo_min_profit_factor: float = Field(default=1.20)
    demo_max_drawdown: float = Field(default=0.08)
    demo_max_stoploss_failures: int = Field(default=0)
    demo_initial_capital: int = Field(default=1_000_000)
    auto_trading_enabled: bool = Field(default=True)
    auto_trading_live_enabled: bool = Field(default=False)
    auto_trading_interval_sec: float = Field(default=3.0)
    auto_trading_min_history: int = Field(default=6)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    learning_log_dir: Path = Field(default=Path("./logs/learning"))
    learning_dataset_dir: Path = Field(default=Path("./data/learning"))
    model_feature_logging: bool = Field(default=True)
    decision_trace_logging: bool = Field(default=True)
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: int = Field(default=8080)
    env_file_path: Path = Field(default=Path(".env"))

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

    @field_validator("rule_change_apply_target")
    @classmethod
    def validate_rule_change_apply_target(cls, value: str) -> str:
        if value != "demo":
            raise ValueError("RULE_CHANGE_APPLY_TARGET must be demo; live direct apply is forbidden")
        return value

    @field_validator("trading_profile")
    @classmethod
    def validate_trading_profile(cls, value: str) -> str:
        if value not in TRADING_PROFILES:
            allowed = ", ".join(sorted(TRADING_PROFILES))
            raise ValueError(f"TRADING_PROFILE must be one of: {allowed}")
        return value

    @field_validator("trading_fee_rate")
    @classmethod
    def validate_trading_fee_rate(cls, value: float) -> float:
        if value < 0 or value > 0.01:
            raise ValueError("TRADING_FEE_RATE must be between 0 and 0.01")
        return value

    @field_validator("min_order_amount_krw")
    @classmethod
    def validate_min_order_amount_krw(cls, value: float) -> float:
        if value < 0:
            raise ValueError("MIN_ORDER_AMOUNT_KRW must be greater than or equal to 0")
        return value

    @field_validator("profile_min_net_edge_pct")
    @classmethod
    def validate_profile_min_net_edge_pct(cls, value: float) -> float:
        if value < 0 or value > 0.05:
            raise ValueError("PROFILE_MIN_NET_EDGE_PCT must be between 0 and 0.05")
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
    rule_review_enabled: bool
    rule_review_window_days: int
    rule_review_min_trades: int
    rule_review_min_stoplosses: int
    rule_change_max_params_per_run: int
    rule_change_apply_target: str
    rule_change_require_manual_approval: bool
    external_context_enabled: bool
    onchain_context_source: str
    onchain_context_url: str
    onchain_state: str
    onchain_active_addresses_change_pct: float
    onchain_exchange_netflow_state: str
    etf_context_source: str
    etf_context_url: str
    etf_state: str
    etf_flow_usd: float
    no_trade_adaptive_enabled: bool
    no_trade_relax_after_cycles: int
    no_trade_relax_min_score: float
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
    trading_profile: str
    trading_fee_rate: float
    min_order_amount_krw: float
    profile_min_net_edge_pct: float
    min_cash_reserve: int
    max_daily_loss: int
    max_slippage_bps: int
    max_spread_bps: int
    cooldown_seconds: int
    reentry_block_seconds: int
    safe_mode_on_restart: bool
    restart_notify: bool
    restart_hard_stop_threshold: int
    restart_state_path: Path
    auto_promote_to_live: bool
    promotion_require_manual_approval: bool
    demo_min_days: int
    demo_min_trades: int
    demo_min_win_rate: float
    demo_min_profit_factor: float
    demo_max_drawdown: float
    demo_max_stoploss_failures: int
    demo_initial_capital: int
    auto_trading_enabled: bool
    auto_trading_live_enabled: bool
    auto_trading_interval_sec: float
    auto_trading_min_history: int
    log_level: str
    log_format: str
    learning_log_dir: Path
    learning_dataset_dir: Path
    model_feature_logging: bool
    decision_trace_logging: bool
    dashboard_host: str
    dashboard_port: int
    env_file_path: Path


def load_settings(*, env_file: Path | None = None) -> AppSettings:
    env_values = _read_env_file(env_file or Path(os.getenv("ENV_FILE_PATH", ".env")))

    trading_profile = _setting("TRADING_PROFILE", "scalping", env_values)
    try:
        profile_spec = get_trading_profile(trading_profile)
    except ValueError as exc:
        raise SettingsError(str(exc)) from exc

    payload = {
        "app_env": _setting("APP_ENV", "production", env_values),
        "app_name": _setting("APP_NAME", "upbit-auto-trader", env_values),
        "app_timezone": _setting("APP_TIMEZONE", "Asia/Seoul", env_values),
        "trading_mode": _setting("TRADING_MODE", "demo", env_values),
        "learning_enabled": _parse_bool(_setting("LEARNING_ENABLED", "true", env_values)),
        "rule_review_enabled": _parse_bool(_setting("RULE_REVIEW_ENABLED", "true", env_values)),
        "rule_review_window_days": int(_setting("RULE_REVIEW_WINDOW_DAYS", "14", env_values)),
        "rule_review_min_trades": int(_setting("RULE_REVIEW_MIN_TRADES", "100", env_values)),
        "rule_review_min_stoplosses": int(_setting("RULE_REVIEW_MIN_STOPLOSSES", "20", env_values)),
        "rule_change_max_params_per_run": int(_setting("RULE_CHANGE_MAX_PARAMS_PER_RUN", "3", env_values)),
        "rule_change_apply_target": _setting("RULE_CHANGE_APPLY_TARGET", "demo", env_values),
        "rule_change_require_manual_approval": _parse_bool(
            _setting("RULE_CHANGE_REQUIRE_MANUAL_APPROVAL", "true", env_values),
        ),
        "external_context_enabled": _parse_bool(_setting("EXTERNAL_CONTEXT_ENABLED", "true", env_values)),
        "onchain_context_source": _setting("ONCHAIN_CONTEXT_SOURCE", "manual", env_values),
        "onchain_context_url": _setting("ONCHAIN_CONTEXT_URL", "", env_values),
        "onchain_state": _setting("ONCHAIN_STATE", "neutral", env_values),
        "onchain_active_addresses_change_pct": float(
            _setting("ONCHAIN_ACTIVE_ADDRESSES_CHANGE_PCT", "0.0", env_values),
        ),
        "onchain_exchange_netflow_state": _setting("ONCHAIN_EXCHANGE_NETFLOW_STATE", "neutral", env_values),
        "etf_context_source": _setting("ETF_CONTEXT_SOURCE", "manual", env_values),
        "etf_context_url": _setting("ETF_CONTEXT_URL", "", env_values),
        "etf_state": _setting("ETF_STATE", "neutral", env_values),
        "etf_flow_usd": float(_setting("ETF_FLOW_USD", "0.0", env_values)),
        "no_trade_adaptive_enabled": _parse_bool(_setting("NO_TRADE_ADAPTIVE_ENABLED", "true", env_values)),
        "no_trade_relax_after_cycles": int(_setting("NO_TRADE_RELAX_AFTER_CYCLES", "100", env_values)),
        "no_trade_relax_min_score": float(_setting("NO_TRADE_RELAX_MIN_SCORE", "0.30", env_values)),
        "trade_market": _setting("TRADE_MARKET", "KRW-XRP", env_values),
        "trade_coin": _setting("TRADE_COIN", "XRP", env_values),
        "upbit_access_key": _setting("UPBIT_ACCESS_KEY", "", env_values),
        "upbit_secret_key": _setting("UPBIT_SECRET_KEY", "", env_values),
        "upbit_base_url": _setting("UPBIT_BASE_URL", "https://api.upbit.com", env_values),
        "upbit_ws_public_url": _setting("UPBIT_WS_PUBLIC_URL", "wss://api.upbit.com/websocket/v1", env_values),
        "upbit_ws_private_url": os.getenv(
            "UPBIT_WS_PRIVATE_URL",
            env_values.get("UPBIT_WS_PRIVATE_URL", "wss://api.upbit.com/websocket/v1/private"),
        ),
        "telegram_bot_token": _setting("TELEGRAM_BOT_TOKEN", "", env_values),
        "telegram_chat_id": _setting("TELEGRAM_CHAT_ID", "", env_values),
        "telegram_notify_in_demo": _parse_bool(_setting("TELEGRAM_NOTIFY_IN_DEMO", "true", env_values)),
        "buy_ratio_weak": float(_setting("BUY_RATIO_WEAK", "0.08", env_values)),
        "buy_ratio_medium": float(_setting("BUY_RATIO_MEDIUM", "0.18", env_values)),
        "buy_ratio_strong": float(_setting("BUY_RATIO_STRONG", "0.35", env_values)),
        "buy_ratio_very_strong": float(_setting("BUY_RATIO_VERY_STRONG", "0.55", env_values)),
        "sell_ratio_weak": float(_setting("SELL_RATIO_WEAK", "0.12", env_values)),
        "sell_ratio_medium": float(_setting("SELL_RATIO_MEDIUM", "0.28", env_values)),
        "sell_ratio_strong": float(_setting("SELL_RATIO_STRONG", "0.45", env_values)),
        "sell_ratio_very_strong": float(_setting("SELL_RATIO_VERY_STRONG", "0.70", env_values)),
        "stop_loss_weak": float(_setting("STOP_LOSS_WEAK", "0.008", env_values)),
        "stop_loss_medium": float(_setting("STOP_LOSS_MEDIUM", "0.012", env_values)),
        "stop_loss_strong": float(_setting("STOP_LOSS_STRONG", "0.018", env_values)),
        "stop_loss_very_strong": float(_setting("STOP_LOSS_VERY_STRONG", "0.022", env_values)),
        "validation_window_sec": int(
            _setting("VALIDATION_WINDOW_SEC", str(profile_spec.validation_window_sec), env_values),
        ),
        "min_expected_return_pct": float(
            _setting("MIN_EXPECTED_RETURN_PCT", str(profile_spec.min_expected_return_pct), env_values),
        ),
        "trading_profile": trading_profile,
        "trading_fee_rate": float(_setting("TRADING_FEE_RATE", "0.0005", env_values)),
        "min_order_amount_krw": float(_setting("MIN_ORDER_AMOUNT_KRW", "5000", env_values)),
        "profile_min_net_edge_pct": float(
            _setting(
                "PROFILE_MIN_NET_EDGE_PCT",
                _setting("SCALPING_MIN_NET_EDGE_PCT", str(profile_spec.min_net_edge_pct), env_values),
                env_values,
            ),
        ),
        "min_cash_reserve": int(_setting("MIN_CASH_RESERVE", "100000", env_values)),
        "max_daily_loss": int(_setting("MAX_DAILY_LOSS", "150000", env_values)),
        "max_slippage_bps": int(_setting("MAX_SLIPPAGE_BPS", "20", env_values)),
        "max_spread_bps": int(_setting("MAX_SPREAD_BPS", "15", env_values)),
        "cooldown_seconds": int(_setting("COOLDOWN_SECONDS", "60", env_values)),
        "reentry_block_seconds": int(_setting("REENTRY_BLOCK_SECONDS", "180", env_values)),
        "safe_mode_on_restart": _parse_bool(_setting("SAFE_MODE_ON_RESTART", "true", env_values)),
        "restart_notify": _parse_bool(_setting("RESTART_NOTIFY", "true", env_values)),
        "restart_hard_stop_threshold": int(_setting("RESTART_HARD_STOP_THRESHOLD", "3", env_values)),
        "restart_state_path": Path(_setting("RESTART_STATE_PATH", "./logs/recovery/restart-state.json", env_values)),
        "auto_promote_to_live": _parse_bool(_setting("AUTO_PROMOTE_TO_LIVE", "false", env_values)),
        "promotion_require_manual_approval": _parse_bool(
            _setting("PROMOTION_REQUIRE_MANUAL_APPROVAL", "true", env_values),
        ),
        "demo_min_days": int(_setting("DEMO_MIN_DAYS", "14", env_values)),
        "demo_min_trades": int(_setting("DEMO_MIN_TRADES", "100", env_values)),
        "demo_min_win_rate": float(_setting("DEMO_MIN_WIN_RATE", "0.52", env_values)),
        "demo_min_profit_factor": float(_setting("DEMO_MIN_PROFIT_FACTOR", "1.20", env_values)),
        "demo_max_drawdown": float(_setting("DEMO_MAX_DRAWDOWN", "0.08", env_values)),
        "demo_max_stoploss_failures": int(_setting("DEMO_MAX_STOPLOSS_FAILURES", "0", env_values)),
        "demo_initial_capital": int(_setting("DEMO_INITIAL_CAPITAL", "1000000", env_values)),
        "auto_trading_enabled": _parse_bool(_setting("AUTO_TRADING_ENABLED", "true", env_values)),
        "auto_trading_live_enabled": _parse_bool(_setting("AUTO_TRADING_LIVE_ENABLED", "false", env_values)),
        "auto_trading_interval_sec": float(
            _setting("AUTO_TRADING_INTERVAL_SEC", str(profile_spec.auto_interval_sec), env_values),
        ),
        "auto_trading_min_history": int(
            _setting("AUTO_TRADING_MIN_HISTORY", str(profile_spec.auto_min_history), env_values),
        ),
        "log_level": _setting("LOG_LEVEL", "INFO", env_values),
        "log_format": _setting("LOG_FORMAT", "json", env_values),
        "learning_log_dir": Path(_setting("LEARNING_LOG_DIR", "./logs/learning", env_values)),
        "learning_dataset_dir": Path(_setting("LEARNING_DATASET_DIR", "./data/learning", env_values)),
        "model_feature_logging": _parse_bool(_setting("MODEL_FEATURE_LOGGING", "true", env_values)),
        "decision_trace_logging": _parse_bool(_setting("DECISION_TRACE_LOGGING", "true", env_values)),
        "dashboard_host": _setting("DASHBOARD_HOST", "0.0.0.0", env_values),
        "dashboard_port": int(_setting("DASHBOARD_PORT", "8080", env_values)),
        "env_file_path": env_file or Path(os.getenv("ENV_FILE_PATH", ".env")),
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


def _setting(key: str, default: str, env_values: dict[str, str]) -> str:
    return os.getenv(key, env_values.get(key, default))


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
