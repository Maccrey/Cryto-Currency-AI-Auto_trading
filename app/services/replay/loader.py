from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReplayTick:
    timestamp: str
    price: float
    traded_value: float
    spread_bps: float
    orderbook_imbalance: float
    liquidity_score: float
    regime_score: float


class ReplayFixtureLoader:
    """Load historical replay ticks from JSON fixtures."""

    def load(self, path: Path) -> list[ReplayTick]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [
            ReplayTick(
                timestamp=str(item["timestamp"]),
                price=float(item["price"]),
                traded_value=float(item["traded_value"]),
                spread_bps=float(item["spread_bps"]),
                orderbook_imbalance=float(item["orderbook_imbalance"]),
                liquidity_score=float(item["liquidity_score"]),
                regime_score=float(item["regime_score"]),
            )
            for item in payload
        ]

    def load_market_observations(self, path: Path, *, limit: int = 500) -> list[ReplayTick]:
        if not path.exists():
            return []
        rows: list[dict[str, object]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines()[-max(limit, 0) :]:
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        ticks: list[ReplayTick] = []
        for item in rows:
            try:
                ticks.append(
                    ReplayTick(
                        timestamp=str(item.get("recorded_at") or item.get("timestamp") or ""),
                        price=float(item["trade_price"]),
                        traded_value=float(item.get("traded_value", 0.0)),
                        spread_bps=float(item.get("spread_bps", 0.0)),
                        orderbook_imbalance=float(item.get("orderbook_imbalance", 0.0)),
                        liquidity_score=float(item.get("liquidity_score", 0.5)),
                        regime_score=float(item.get("regime_score", 0.5)),
                    ),
                )
            except (KeyError, TypeError, ValueError):
                continue
        return ticks
