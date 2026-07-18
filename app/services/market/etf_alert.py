from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EtfContextChangeMonitor:
    """Persist an ETF baseline and notify only meaningful, fresh changes."""

    def __init__(self, *, state_path: Path, notifier: Any | None = None) -> None:
        self._state_path = state_path
        self._notifier = notifier

    def observe(self, *, market: str, mode: str, context: dict[str, object]) -> bool:
        etf = context.get("etf")
        if not isinstance(etf, dict) or etf.get("state") in {None, "disabled", "not_applicable"}:
            return False
        current = self._snapshot(etf)
        previous = self._load()
        if previous is None:
            self._save(current)
            return False
        changed = self._changed_fields(previous, current)
        self._save(current)
        if not changed or self._notifier is None:
            return False
        self._notifier.notify_etf_context_changed(
            market=market,
            mode=mode,
            previous=previous,
            current=current,
            changed_fields=changed,
        )
        return True

    @staticmethod
    def _snapshot(etf: dict[str, object]) -> dict[str, object]:
        return {
            "state": str(etf.get("state") or "unknown"),
            "flow_usd": float(etf.get("flow_usd") or 0.0),
            "flow_date": str(etf.get("flow_date") or ""),
            "total_aum_usd": float(etf.get("total_aum_usd") or 0.0),
            "total_holding_coin": float(etf.get("total_holding_coin") or 0.0),
            "daily_volume_usd": float(etf.get("daily_volume_usd") or 0.0),
            "data_status": str(etf.get("data_status") or "unknown"),
        }

    @staticmethod
    def _changed_fields(previous: dict[str, object], current: dict[str, object]) -> list[str]:
        changed: list[str] = []
        for key in ("state", "flow_date", "data_status"):
            if previous.get(key) != current.get(key):
                changed.append(key)
        if abs(float(current["flow_usd"]) - float(previous.get("flow_usd") or 0.0)) >= 1.0:
            changed.append("flow_usd")
        for key in ("total_aum_usd", "total_holding_coin", "daily_volume_usd"):
            old = float(previous.get(key) or 0.0)
            new = float(current[key])
            if old == 0.0 and new != 0.0 or old != 0.0 and abs(new - old) / abs(old) >= 0.02:
                changed.append(key)
        return changed

    def _load(self) -> dict[str, object] | None:
        if not self._state_path.exists():
            return None
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _save(self, snapshot: dict[str, object]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True), encoding="utf-8")
