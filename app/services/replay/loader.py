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

