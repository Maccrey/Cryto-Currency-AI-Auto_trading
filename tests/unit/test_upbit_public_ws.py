from __future__ import annotations

import asyncio

from app.integrations.upbit.public_ws import (
    MarketSnapshotEvent,
    PublicWebSocketClient,
)


class FakeWebSocketConnection:
    def __init__(self) -> None:
        self.sent_messages: list[object] = []
        self.closed = False

    async def send_json(self, payload: object) -> None:
        self.sent_messages.append(payload)

    async def recv_json(self) -> dict[str, object]:
        return {
            "code": "KRW-XRP",
            "trade_price": 821.4,
            "signed_change_rate": 0.012,
            "timestamp": 1713427200000,
            "acc_trade_price_24h": 123456789.0,
        }

    async def close(self) -> None:
        self.closed = True


def test_public_ws_reconnect_restores_subscription() -> None:
    async def scenario() -> None:
        first = FakeWebSocketConnection()
        second = FakeWebSocketConnection()
        connections = iter([first, second])

        async def factory() -> FakeWebSocketConnection:
            return next(connections)

        client = PublicWebSocketClient(connection_factory=factory, ticket="test-ticket")
        client.subscribe_ticker(["KRW-XRP"])

        await client.connect()
        await client.reconnect()

        expected_payload = [
            {"ticket": "test-ticket"},
            {"type": "ticker", "codes": ["KRW-XRP"]},
        ]
        assert first.sent_messages == [expected_payload]
        assert first.closed is True
        assert second.sent_messages == [expected_payload]

    asyncio.run(scenario())


def test_public_ws_parses_market_snapshot_event() -> None:
    async def scenario() -> None:
        connection = FakeWebSocketConnection()

        async def factory() -> FakeWebSocketConnection:
            return connection

        client = PublicWebSocketClient(connection_factory=factory, ticket="test-ticket")
        client.subscribe_ticker(["KRW-XRP"])
        await client.connect()

        snapshot = await client.receive_market_snapshot()

        assert snapshot == MarketSnapshotEvent(
            market="KRW-XRP",
            trade_price=821.4,
            signed_change_rate=0.012,
            timestamp=1713427200000,
            acc_trade_price_24h=123456789.0,
        )

    asyncio.run(scenario())
