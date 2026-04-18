from __future__ import annotations

from app.services.recovery.open_orders import OpenOrderReconciler, OpenOrderReconcileError


class StubUpbitClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get(self, path: str, *, params=None):
        self.calls.append((path, params))
        return self.payload


def test_open_order_reconciler_fetches_open_orders_for_market() -> None:
    client = StubUpbitClient(
        [
            {"uuid": "1", "market": "KRW-XRP", "side": "bid", "state": "wait"},
            {"uuid": "2", "market": "KRW-XRP", "side": "ask", "state": "watch"},
        ],
    )
    reconciler = OpenOrderReconciler(upbit_client=client, trade_market="KRW-XRP")

    result = reconciler.reconcile()

    assert client.calls == [
        (
            "/v1/orders/open",
            {"market": "KRW-XRP", "states[]": ["wait", "watch"]},
        )
    ]
    assert result == {
        "open_order_count": 2,
        "markets": ["KRW-XRP"],
        "order_ids": ["1", "2"],
        "status": "reconciled",
    }


def test_open_order_reconciler_rejects_non_list_payload() -> None:
    reconciler = OpenOrderReconciler(
        upbit_client=StubUpbitClient({"uuid": "1"}),
        trade_market="KRW-XRP",
    )

    try:
        reconciler.reconcile()
    except OpenOrderReconcileError as exc:
        assert "list" in str(exc)
    else:
        raise AssertionError("Expected reconcile failure for non-list payload")

