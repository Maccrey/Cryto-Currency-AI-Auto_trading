from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.market.trend import MarketTrendClassifier


@dataclass(frozen=True)
class UpbitCandleSnapshot:
    market: str
    trade_price: float
    recorded_at: str
    opening_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    candle_acc_trade_volume: float | None = None
    candle_acc_trade_price: float | None = None


class UpbitHistoricalCandleProvider:
    """Fetch recent public Upbit candles for runtime warmup."""

    def __init__(
        self,
        *,
        base_url: str,
        unit_minutes: int = 60,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._unit_minutes = unit_minutes
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
        )

    def fetch_recent(self, *, market: str, count: int) -> list[UpbitCandleSnapshot]:
        response = self._client.get(
            f"/v1/candles/minutes/{self._unit_minutes}",
            params={"market": market, "count": count},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        candles = [self._to_snapshot(item, fallback_market=market) for item in payload if isinstance(item, dict)]
        return sorted((item for item in candles if item is not None), key=lambda item: item.recorded_at)

    def close(self) -> None:
        self._client.close()

    @classmethod
    def _to_snapshot(cls, payload: dict[str, Any], *, fallback_market: str) -> UpbitCandleSnapshot | None:
        trade_price = cls._optional_float(payload.get("trade_price"))
        kst_recorded_at = payload.get("candle_date_time_kst")
        utc_recorded_at = payload.get("candle_date_time_utc")
        recorded_at = kst_recorded_at or utc_recorded_at
        if trade_price is None or not recorded_at:
            return None
        timezone_suffix = "+09:00" if kst_recorded_at else "+00:00"
        return UpbitCandleSnapshot(
            market=str(payload.get("market") or fallback_market),
            trade_price=trade_price,
            recorded_at=cls._normalize_recorded_at(str(recorded_at), timezone_suffix=timezone_suffix),
            opening_price=cls._optional_float(payload.get("opening_price")),
            high_price=cls._optional_float(payload.get("high_price")),
            low_price=cls._optional_float(payload.get("low_price")),
            candle_acc_trade_volume=cls._optional_float(payload.get("candle_acc_trade_volume")),
            candle_acc_trade_price=cls._optional_float(payload.get("candle_acc_trade_price")),
        )

    @staticmethod
    def _normalize_recorded_at(value: str, *, timezone_suffix: str) -> str:
        if value.endswith("Z") or "+" in value:
            return value
        return f"{value}{timezone_suffix}"

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)


class HistoricalMarketBootstrapService:
    """Seed runtime price history and rule-review observations from recent candles."""

    def __init__(
        self,
        *,
        market: str,
        trading_mode: str,
        candle_provider: UpbitHistoricalCandleProvider,
        market_price_store: MarketPriceStore,
        learning_service: LearningService,
        observation_path: Path,
        trend_classifier: MarketTrendClassifier | None = None,
        candle_count: int = 72,
    ) -> None:
        self._market = market
        self._trading_mode = trading_mode
        self._candle_provider = candle_provider
        self._market_price_store = market_price_store
        self._learning_service = learning_service
        self._observation_path = observation_path
        self._trend_classifier = trend_classifier or MarketTrendClassifier()
        self._candle_count = candle_count

    def bootstrap(self) -> dict[str, object]:
        candles = self._candle_provider.fetch_recent(market=self._market, count=self._candle_count)
        existing_keys = self._existing_observation_keys()
        written_count = 0
        latest_payload: dict[str, object] | None = None
        for candle in candles:
            if candle.market != self._market or candle.trade_price <= 0:
                continue
            self._market_price_store.save_at(
                market=self._market,
                price=candle.trade_price,
                recorded_at=candle.recorded_at,
            )
            payload = self._observation_payload(candle)
            latest_payload = payload
            key = self._observation_key(payload)
            if key in existing_keys:
                continue
            self._learning_service.record_market_observation(payload)
            existing_keys.add(key)
            written_count += 1

        if latest_payload is not None:
            self._learning_service.record(
                LearningEvent(
                    event_name="market_history_bootstrapped",
                    market=self._market,
                    mode=self._trading_mode,
                    payload={
                        "source": "upbit_3d_bootstrap",
                        "candle_count": len(candles),
                        "written_observation_count": written_count,
                        "market_state": latest_payload.get("market_state"),
                        "market_state_label": latest_payload.get("market_state_label"),
                        "box_range_low": latest_payload.get("box_range_low"),
                        "box_range_high": latest_payload.get("box_range_high"),
                    },
                    recorded_at=datetime.now(UTC).isoformat(),
                ),
            )
        return {
            "status": "completed",
            "market": self._market,
            "source": "upbit_3d_bootstrap",
            "candle_count": len(candles),
            "written_observation_count": written_count,
            "latest_market_state": None if latest_payload is None else latest_payload.get("market_state"),
            "latest_market_state_label": None if latest_payload is None else latest_payload.get("market_state_label"),
        }

    def _observation_payload(self, candle: UpbitCandleSnapshot) -> dict[str, object]:
        trend = self._trend_classifier.classify(
            current_price=candle.trade_price,
            history=self._market_price_store.list_history(self._market),
            learning_events=[],
            reference_change_pct=None,
        )
        history = self._market_price_store.list_history(self._market, limit=288)
        price_window = [item.price for item in history]
        return {
            "recorded_at": candle.recorded_at,
            "market": self._market,
            "mode": self._trading_mode,
            "source": "upbit_3d_bootstrap",
            "trade_price": candle.trade_price,
            "opening_price": candle.opening_price,
            "high_price": candle.high_price,
            "low_price": candle.low_price,
            "traded_value": candle.candle_acc_trade_price,
            "candle_acc_trade_volume": candle.candle_acc_trade_volume,
            "candle_acc_trade_price": candle.candle_acc_trade_price,
            "history_count": len(price_window),
            "price_window_low": min(price_window) if price_window else None,
            "price_window_high": max(price_window) if price_window else None,
            "market_state": trend.market_state,
            "market_state_label": trend.market_state_label,
            "box_range_low": trend.box_range_low,
            "box_range_high": trend.box_range_high,
            "market_state_recent_change_pct": trend.recent_change_pct,
            "market_state_source": trend.source,
            "market_state_learning_sample_count": trend.learning_sample_count,
            "market_state_learning_confidence": trend.learning_confidence,
        }

    def _existing_observation_keys(self) -> set[tuple[str, str, str]]:
        if not self._observation_path.exists():
            return set()
        keys: set[tuple[str, str, str]] = set()
        with self._observation_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    keys.add(self._observation_key(payload))
        return keys

    @staticmethod
    def _observation_key(payload: dict[str, object]) -> tuple[str, str, str]:
        return (
            str(payload.get("market") or ""),
            str(payload.get("source") or ""),
            str(payload.get("recorded_at") or ""),
        )
