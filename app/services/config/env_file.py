from __future__ import annotations

from pathlib import Path


SECRET_KEYS = {"UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "TELEGRAM_BOT_TOKEN"}
LIVE_REQUIRED_KEYS = ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]


class EnvFileService:
    """Read and write the local .env file used by the settings screen."""

    def __init__(self, env_path: Path) -> None:
        self._env_path = env_path

    def current(self) -> dict[str, object]:
        values = self._read()
        mode = values.get("TRADING_MODE", "demo")
        missing_for_live = self._missing_for_live(values) if mode == "live" else []
        return {
            "status": "ok",
            "mode": mode,
            "values": self._masked(values),
            "missing_for_live": missing_for_live,
            "env_path": str(self._env_path),
        }

    def save(self, updates: dict[str, object]) -> dict[str, object]:
        values = self._read()
        normalized = {key: str(value).strip() for key, value in updates.items() if value is not None}
        for key in SECRET_KEYS:
            if key in normalized and not normalized[key] and values.get(key):
                normalized[key] = values[key]
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
            masked[key] = "***" if key in SECRET_KEYS and value else value
        return masked
