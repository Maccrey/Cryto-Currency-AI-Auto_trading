from __future__ import annotations

import socket
from pathlib import Path

from app.core.trading_profile import TRADING_PROFILES, get_trading_profile


SECRET_KEYS = {"UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "TELEGRAM_BOT_TOKEN"}
SECRET_MASK = "***"
LIVE_REQUIRED_KEYS = ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]
DEMO_REQUIRED_KEYS = ["TRADING_MODE", "TRADING_PROFILE", "TRADE_MARKET", "TRADE_COIN", "DEMO_INITIAL_CAPITAL"]


class EnvFileService:
    """Read and write the local .env file used by the settings screen."""

    def __init__(self, env_path: Path) -> None:
        self._env_path = env_path

    def current(self) -> dict[str, object]:
        values = self._read()
        display_values = dict(values)
        display_values.setdefault("SERVER_NAME", self._default_server_name())
        for key, value in self._sideways_risk_defaults().items():
            display_values.setdefault(key, value)
        mode = values.get("TRADING_MODE", "demo")
        profile = values.get("TRADING_PROFILE", "scalping")
        missing_for_live = self._missing_for_live(values) if mode == "live" else []
        start_readiness = self.trading_start_readiness(values)
        storage_dir = values.get("STORAGE_DIR", "./storage")
        return {
            "status": "ok",
            "mode": mode,
            "profile": profile,
            "profiles": self._profile_payload(),
            "values": self._masked(display_values),
            "missing_for_live": missing_for_live,
            "start_readiness": start_readiness,
            "env_path": str(self._env_path),
            "data_path_status": {
                "storage_dir": storage_dir,
                "learning_log_dir": values.get("LEARNING_LOG_DIR", f"{storage_dir}/logs/learning"),
                "learning_dataset_dir": values.get("LEARNING_DATASET_DIR", f"{storage_dir}/data/learning"),
                "restart_state_path": values.get(
                    "RESTART_STATE_PATH",
                    f"{storage_dir}/runtime/recovery/restart-state.json",
                ),
            },
            "auto_rule_update": {
                "enabled": values.get("AUTO_RULE_UPDATE_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
                "learning_completion_rate_required": float(
                    values.get("AUTO_RULE_UPDATE_MIN_LEARNING_COMPLETION_RATE", "1.0"),
                ),
                "win_rate_skip_threshold": float(values.get("AUTO_RULE_UPDATE_WIN_RATE_SKIP_THRESHOLD", "0.80")),
            },
        }

    def server_name(self, *, fallback: str = "") -> str:
        saved_name = self._read().get("SERVER_NAME", "").strip()
        if saved_name:
            return saved_name
        fallback = fallback.strip()
        return fallback or self._default_server_name()

    def secret_value(self, key: str) -> dict[str, object]:
        if key not in SECRET_KEYS:
            return {
                "status": "invalid",
                "found": False,
                "key": key,
                "value": "",
                "message": "unsupported secret key",
            }
        value = self._read().get(key, "")
        return {
            "status": "ok",
            "found": bool(value),
            "key": key,
            "value": value,
        }

    def save(self, updates: dict[str, object]) -> dict[str, object]:
        values = self._read()
        normalized = {key: str(value).strip() for key, value in updates.items() if value is not None}
        if not normalized.get("SERVER_NAME"):
            normalized["SERVER_NAME"] = values.get("SERVER_NAME", "").strip() or self._default_server_name()
        for key in SECRET_KEYS:
            if key in normalized and self._is_secret_placeholder(normalized[key]) and values.get(key):
                normalized[key] = values[key]
        if "TELEGRAM_CHAT_ID" in normalized:
            normalized["TELEGRAM_CHAT_ID"] = self._normalize_telegram_chat_id(normalized["TELEGRAM_CHAT_ID"])
        if "TRADE_COIN" in normalized:
            normalized["TRADE_COIN"] = normalized["TRADE_COIN"].upper()
        if "TRADE_MARKET" in normalized:
            normalized["TRADE_MARKET"] = normalized["TRADE_MARKET"].upper()
        self._normalize_trade_market_for_coin(values=values, normalized=normalized)
        normalized.setdefault("LEARNING_ENABLED", "true")
        mode = normalized.get("TRADING_MODE", "demo")
        if mode not in {"demo", "live"}:
            return {
                "status": "invalid",
                "saved": False,
                "missing_for_live": [],
                "message": "TRADING_MODE must be demo or live",
            }
        normalized["TRADING_MODE"] = mode
        normalized["LEARNING_ENABLED"] = "true"
        profile = normalized.get("TRADING_PROFILE", values.get("TRADING_PROFILE", "scalping"))
        try:
            profile_spec = get_trading_profile(profile)
        except ValueError as exc:
            return {
                "status": "invalid",
                "saved": False,
                "missing_for_live": [],
                "message": str(exc),
            }
        normalized["TRADING_PROFILE"] = profile
        for key, value in self._profile_defaults(profile_spec).items():
            normalized.setdefault(key, value)

        missing_for_live = self._missing_for_live(normalized) if mode == "live" else []
        if missing_for_live:
            return {
                "status": "missing_required",
                "saved": False,
                "missing_for_live": missing_for_live,
                "message": "live mode requires Upbit API keys",
            }

        values.update(normalized)
        self._write(values)
        return {
            "status": "saved",
            "saved": True,
            "profile": profile,
            "missing_for_live": [],
            "start_readiness": self.trading_start_readiness(values),
            "message": "settings saved",
        }

    def trading_start_readiness(self, values: dict[str, str] | None = None) -> dict[str, object]:
        current_values = self._read() if values is None else values
        mode = current_values.get("TRADING_MODE", "demo").strip()
        missing = [key for key in DEMO_REQUIRED_KEYS if not current_values.get(key, "").strip()]
        invalid: list[str] = []

        if mode not in {"demo", "live"}:
            invalid.append("TRADING_MODE")
        try:
            get_trading_profile(current_values.get("TRADING_PROFILE", ""))
        except ValueError:
            invalid.append("TRADING_PROFILE")
        try:
            if int(current_values.get("DEMO_INITIAL_CAPITAL", "0")) <= 0:
                invalid.append("DEMO_INITIAL_CAPITAL")
        except ValueError:
            invalid.append("DEMO_INITIAL_CAPITAL")
        if not self._market_matches_coin(current_values):
            invalid.append("TRADE_MARKET")

        if mode == "live":
            missing.extend(self._missing_for_live(current_values))

        missing = sorted(set(missing))
        invalid = sorted(set(invalid))
        return {
            "ready": not missing and not invalid,
            "mode": mode,
            "missing": missing,
            "invalid": invalid,
            "required": sorted(set(DEMO_REQUIRED_KEYS + (LIVE_REQUIRED_KEYS if mode == "live" else []))),
            "message": self._readiness_message(mode=mode, missing=missing, invalid=invalid),
        }

    def _read(self) -> dict[str, str]:
        if not self._env_path.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in self._env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _write(self, values: dict[str, str]) -> None:
        self._env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{key}={values[key]}" for key in sorted(values)]
        self._env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _missing_for_live(values: dict[str, str]) -> list[str]:
        return [key for key in LIVE_REQUIRED_KEYS if not values.get(key, "").strip()]

    @staticmethod
    def _normalize_trade_market_for_coin(*, values: dict[str, str], normalized: dict[str, str]) -> None:
        coin = normalized.get("TRADE_COIN") or values.get("TRADE_COIN", "")
        market = normalized.get("TRADE_MARKET") or values.get("TRADE_MARKET", "")
        if not coin:
            return
        if (
            not market
            or market == "KRW-XRP"
            or market.startswith("KRW-")
        ):
            normalized["TRADE_MARKET"] = f"KRW-{coin}"

    @staticmethod
    def _market_matches_coin(values: dict[str, str]) -> bool:
        market = values.get("TRADE_MARKET", "").strip().upper()
        coin = values.get("TRADE_COIN", "").strip().upper()
        if not market or not coin:
            return True
        if "-" not in market:
            return False
        return market.split("-")[-1] == coin

    @staticmethod
    def _readiness_message(*, mode: str, missing: list[str], invalid: list[str]) -> str:
        if not missing and not invalid:
            return "trading can be started"
        problems = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        if invalid:
            problems.append("invalid: " + ", ".join(invalid))
        prefix = "live mode" if mode == "live" else "demo mode"
        return f"{prefix} start requirements are not satisfied; " + "; ".join(problems)

    @staticmethod
    def _masked(values: dict[str, str]) -> dict[str, str]:
        masked: dict[str, str] = {}
        for key, value in values.items():
            masked[key] = SECRET_MASK if key in SECRET_KEYS and value else value
        return masked

    @staticmethod
    def _is_secret_placeholder(value: str) -> bool:
        if not value:
            return True
        return set(value) == {"*"}

    @staticmethod
    def _normalize_telegram_chat_id(value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("telegram:group:"):
            return normalized.removeprefix("telegram:group:").strip()
        if normalized.startswith("telegram:user:"):
            return normalized.removeprefix("telegram:user:").strip()
        return normalized

    @staticmethod
    def _default_server_name() -> str:
        hostname = socket.gethostname().strip()
        if hostname:
            return hostname.split(".", 1)[0]
        return "local-trading-server"

    @staticmethod
    def _profile_defaults(profile_spec) -> dict[str, str]:
        return {
            "AUTO_TRADING_INTERVAL_SEC": str(profile_spec.auto_interval_sec),
            "AUTO_TRADING_MIN_HISTORY": str(profile_spec.auto_min_history),
            "PROFILE_MIN_NET_EDGE_PCT": str(profile_spec.min_net_edge_pct),
            "VALIDATION_WINDOW_SEC": str(profile_spec.validation_window_sec),
            "MIN_EXPECTED_RETURN_PCT": str(profile_spec.min_expected_return_pct),
            "STOP_LOSS_WEAK": str(profile_spec.fixed_stop_loss_pct),
            "STOP_LOSS_MEDIUM": str(profile_spec.fixed_stop_loss_pct),
            "STOP_LOSS_STRONG": str(profile_spec.fixed_stop_loss_pct),
            "STOP_LOSS_VERY_STRONG": str(profile_spec.fixed_stop_loss_pct),
        }

    @staticmethod
    def _sideways_risk_defaults() -> dict[str, str]:
        return {
            "SIDEWAYS_RISK_GUARD_ENABLED": "true",
            "SIDEWAYS_PRICE_RANGE_PCT": "0.002",
            "SIDEWAYS_TRADED_VALUE_RANGE_PCT": "0.003",
            "SIDEWAYS_MAX_AVG_ABS_RETURN_PCT": "0.001",
            "SIDEWAYS_SCALE_IN_MIN_DISCOUNT_PCT": "0.003",
        }

    @staticmethod
    def _profile_payload() -> list[dict[str, object]]:
        return [
            {
                "key": spec.key,
                "label": spec.label,
                "description": spec.description,
                "auto_interval_sec": spec.auto_interval_sec,
                "auto_min_history": spec.auto_min_history,
                "min_net_edge_pct": spec.min_net_edge_pct,
                "validation_window_sec": spec.validation_window_sec,
                "min_expected_return_pct": spec.min_expected_return_pct,
                "fixed_stop_loss_pct": spec.fixed_stop_loss_pct,
            }
            for spec in TRADING_PROFILES.values()
        ]
