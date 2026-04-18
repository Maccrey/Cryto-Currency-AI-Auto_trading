from __future__ import annotations

import asyncio

from app.integrations.upbit.private_ws import (
    AccountSnapshotEvent,
    OrderSnapshotEvent,
    PrivateWebSocketClient,
)


class FakePrivateWebSocketConnection:
    def __init__(self, messages: list[dict[str, object]] | None = None) -> None:
        self.sent_messages: list[object] = []
        self.closed = False
        self._messages = list(messages or [])

    async def send_json(self, payload: object) -> None:
        self.sent_messages.append(payload)

    async def recv_json(self) -> dict[str, object]:
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True


def test_private_ws_reconnect_restores_state_subscriptions() -> None:
    async def scenario() -> None:
        first = FakePrivateWebSocketConnection()
        second = FakePrivateWebSocketConnection()
        connections = iter([first, second])

        async def factory() -> FakePrivateWebSocketConnection:
            return next(connections)

        client = PrivateWebSocketClient(connection_factory=factory, ticket="private-ticket")
        client.subscribe_my_order(["KRW-XRP"])
        client.subscribe_my_asset()

        await client.connect()
        await client.reconnect()

        expected_payload = [
            {"ticket": "private-ticket"},
            {"type": "myOrder", "codes": ["KRW-XRP"]},
            {"type": "myAsset"},
        ]
        assert first.sent_messages == [expected_payload]
        assert first.closed is True
        assert second.sent_messages == [expected_payload]

    asyncio.run(scenario())


def test_private_ws_reads_account_snapshot() -> None:
    async def scenario() -> None:
        connection = FakePrivateWebSocketConnection(
            messages=[
                {
                    "type": "myAsset",
                    "currency": "KRW",
                    "balance": "300000.0",
                    "locked": "0.0",
                    "avg_buy_price": "0.0",
                }
            ],
        )

        async def factory() -> FakePrivateWebSocketConnection:
            return connection

        client = PrivateWebSocketClient(connection_factory=factory, ticket="private-ticket")
        client.subscribe_my_asset()
        await client.connect()

        snapshot = await client.receive_account_snapshot()

        assert snapshot == AccountSnapshotEvent(
            currency="KRW",
            balance=300000.0,
            locked=0.0,
            avg_buy_price=0.0,
        )

    asyncio.run(scenario())


def test_private_ws_reads_order_snapshot() -> None:
    async def scenario() -> None:
        connection = FakePrivateWebSocketConnection(
            messages=[
                {
                    "type": "myOrder",
                    "code": "KRW-XRP",
                    "side": "bid",
                    "state": "wait",
                    "created_at": "2026-04-18T09:10:00+09:00",
                    "uuid": "order-1",
                    "price": "820.0",
                    "volume": "150.0",
                    "remaining_volume": "150.0",
                }
            ],
        )

        async def factory() -> FakePrivateWebSocketConnection:
            return connection

        client = PrivateWebSocketClient(connection_factory=factory, ticket="private-ticket")
        client.subscribe_my_order(["KRW-XRP"])
        await client.connect()

        snapshot = await client.receive_order_snapshot()

        assert snapshot == OrderSnapshotEvent(
            market="KRW-XRP",
            side="bid",
            state="wait",
            created_at="2026-04-18T09:10:00+09:00",
            order_id="order-1",
            price=820.0,
            volume=150.0,
            remaining_volume=150.0,
        )

    asyncio.run(scenario())
