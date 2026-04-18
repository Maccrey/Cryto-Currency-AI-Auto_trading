from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.integrations.upbit.public_ws import ReconnectManager, WebSocketConnection


@dataclass(frozen=True)
class AccountSnapshotEvent:
    currency: str
    balance: float
    locked: float
    avg_buy_price: float


@dataclass(frozen=True)
class OrderSnapshotEvent:
    market: str
    side: str
    state: str
    created_at: str
    order_id: str
    price: float
    volume: float
    remaining_volume: float


class PrivateWebSocketClient:
    """Track private subscriptions and restore them after reconnect."""

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
        self._order_codes: list[str] = []
        self._asset_subscription_enabled = False

    def subscribe_my_order(self, codes: list[str]) -> None:
        self._order_codes = list(codes)

    def subscribe_my_asset(self) -> None:
        self._asset_subscription_enabled = True

    async def connect(self) -> None:
        self._connection = await self._connection_factory()
        await self._restore_subscriptions(self._connection)

    async def reconnect(self) -> None:
        self._connection = await self._reconnect_manager.reconnect(
            self._connection,
            self._restore_subscriptions,
        )

    async def receive_account_snapshot(self) -> AccountSnapshotEvent:
        payload = await self._receive_payload(expected_type="myAsset")
        return AccountSnapshotEvent(
            currency=str(payload["currency"]),
            balance=float(payload["balance"]),
            locked=float(payload["locked"]),
            avg_buy_price=float(payload["avg_buy_price"]),
        )

    async def receive_order_snapshot(self) -> OrderSnapshotEvent:
        payload = await self._receive_payload(expected_type="myOrder")
        return OrderSnapshotEvent(
            market=str(payload["code"]),
            side=str(payload["side"]),
            state=str(payload["state"]),
            created_at=str(payload["created_at"]),
            order_id=str(payload["uuid"]),
            price=float(payload["price"]),
            volume=float(payload["volume"]),
            remaining_volume=float(payload["remaining_volume"]),
        )

    async def _receive_payload(self, expected_type: str) -> dict[str, object]:
        if self._connection is None:
            raise RuntimeError("Private websocket connection is not established")

        payload = await self._connection.recv_json()
        if payload.get("type") != expected_type:
            raise RuntimeError(f"Expected {expected_type} payload, got {payload.get('type')}")
        return payload

    async def _restore_subscriptions(self, connection: WebSocketConnection) -> None:
        payload: list[dict[str, object]] = [{"ticket": self._ticket}]

        if self._order_codes:
            payload.append({"type": "myOrder", "codes": self._order_codes})
        if self._asset_subscription_enabled:
            payload.append({"type": "myAsset"})

        if len(payload) > 1:
            await connection.send_json(payload)
