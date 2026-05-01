from __future__ import annotations

from pathlib import Path

from app.core.trading_profile import TRADING_PROFILES, get_trading_profile


SECRET_KEYS = {"UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "TELEGRAM_BOT_TOKEN"}
SECRET_MASK = "***"
LIVE_REQUIRED_KEYS = ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]


class EnvFileService:
    """Read and write the local .env file used by the settings screen."""

    def __init__(self, env_path: Path) -> None:
        self._env_path = env_path

    def current(self) -> dict[str, object]:
        values = self._read()
        mode = values.get("TRADING_MODE", "demo")
        profile = values.get("TRADING_PROFILE", "scalping")
        missing_for_live = self._missing_for_live(values) if mode == "live" else []
        return {
            "status": "ok",
            "mode": mode,
            "profile": profile,
            "profiles": self._profile_payload(),
            "values": self._masked(values),
            "missing_for_live": missing_for_live,
            "env_path": str(self._env_path),
        }

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
        for key in SECRET_KEYS:
            if key in normalized and self._is_secret_placeholder(normalized[key]) and values.get(key):
                normalized[key] = values[key]
        if "TELEGRAM_CHAT_ID" in normalized:
            normalized["TELEGRAM_CHAT_ID"] = self._normalize_telegram_chat_id(normalized["TELEGRAM_CHAT_ID"])
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
            "message": "settings saved",
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
    def _profile_defaults(profile_spec) -> dict[str, str]:
        return {
            "AUTO_TRADING_INTERVAL_SEC": str(profile_spec.auto_interval_sec),
            "AUTO_TRADING_MIN_HISTORY": str(profile_spec.auto_min_history),
            "PROFILE_MIN_NET_EDGE_PCT": str(profile_spec.min_net_edge_pct),
            "VALIDATION_WINDOW_SEC": str(profile_spec.validation_window_sec),
            "MIN_EXPECTED_RETURN_PCT": str(profile_spec.min_expected_return_pct),
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
            }
            for spec in TRADING_PROFILES.values()
        ]
