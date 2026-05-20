from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable


class TradingUptimeStore:
    """Persist cumulative auto-trading runtime across process restarts."""

    def __init__(
        self,
        *,
        path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._path = path
        self._clock = clock or (lambda: datetime.now().astimezone())

    def start(self) -> datetime:
        now = self._clock()
        state = self._load()
        if state.get("running_since") is None:
            state["running_since"] = now.isoformat()
            self._save(state)
        return self._parse_datetime(str(state["running_since"])) or now

    def stop(self) -> None:
        now = self._clock()
        state = self._load()
        running_since = self._parse_datetime(str(state.get("running_since") or ""))
        accumulated_sec = float(state.get("accumulated_sec") or 0.0)
        if running_since is not None:
            accumulated_sec += max((now - running_since).total_seconds(), 0.0)
        self._save({"accumulated_sec": int(accumulated_sec), "running_since": None})

    def uptime_sec(self, *, fallback_started_at: datetime | None = None) -> int:
        now = self._clock()
        state = self._load()
        accumulated_sec = float(state.get("accumulated_sec") or 0.0)
        running_since = self._parse_datetime(str(state.get("running_since") or ""))
        if running_since is None:
            running_since = fallback_started_at
        if running_since is not None:
            accumulated_sec += max((now - running_since).total_seconds(), 0.0)
        return max(int(accumulated_sec), 0)

    def reset(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def _load(self) -> dict[str, object]:
        if not self._path.exists():
            return {"accumulated_sec": 0, "running_since": None}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"accumulated_sec": 0, "running_since": None}
        if not isinstance(payload, dict):
            return {"accumulated_sec": 0, "running_since": None}
        return payload

    def _save(self, state: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
