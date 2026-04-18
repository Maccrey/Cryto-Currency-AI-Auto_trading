from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol


class WebSocketConnection(Protocol):
    async def send_json(self, payload: object) -> None: ...

    async def recv_json(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...


@dataclass(frozen=True)
class MarketSnapshotEvent:
    market: str
    trade_price: float
    signed_change_rate: float
    timestamp: int
    acc_trade_price_24h: float


class ReconnectManager:
    """Reconnect and delegate subscription restoration to the caller."""

    def __init__(
        self,
        connection_factory: Callable[[], Awaitable[WebSocketConnection]],
    ) -> None:
        self._connection_factory = connection_factory

    async def reconnect(
        self,
        current_connection: WebSocketConnection | None,
        restore_callback: Callable[[WebSocketConnection], Awaitable[None]],
    ) -> WebSocketConnection:
        if current_connection is not None:
            await current_connection.close()

        new_connection = await self._connection_factory()
        await restore_callback(new_connection)
        return new_connection


class PublicWebSocketClient:
    """Track current public-market subscriptions and restore them after reconnect."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Awaitable[WebSocketConnection]],
        ticket: str,
    ) -> None:
        self._connection_factory = connection_factory
        self._reconnect_manager = ReconnectManager(connection_factory)
        self._ticket = ticket
        self._connection: WebSocketConnection | None = None
        self._ticker_codes: list[str] = []

    def subscribe_ticker(self, codes: list[str]) -> None:
        self._ticker_codes = list(codes)

    async def connect(self) -> None:
        self._connection = await self._connection_factory()
        await self._restore_subscriptions(self._connection)

    async def reconnect(self) -> None:
        self._connection = await self._reconnect_manager.reconnect(
            self._connection,
            self._restore_subscriptions,
        )

    async def receive_market_snapshot(self) -> MarketSnapshotEvent:
        if self._connection is None:
            raise RuntimeError("Public websocket connection is not established")

        payload = await self._connection.recv_json()
        return MarketSnapshotEvent(
            market=str(payload["code"]),
            trade_price=float(payload["trade_price"]),
            signed_change_rate=float(payload["signed_change_rate"]),
            timestamp=int(payload["timestamp"]),
            acc_trade_price_24h=float(payload["acc_trade_price_24h"]),
        )

    async def _restore_subscriptions(self, connection: WebSocketConnection) -> None:
        if not self._ticker_codes:
            return

        await connection.send_json(
            [
                {"ticket": self._ticket},
                {"type": "ticker", "codes": self._ticker_codes},
            ],
        )
