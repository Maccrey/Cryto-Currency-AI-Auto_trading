from __future__ import annotations

import httpx

from app.integrations.upbit.auth import UpbitAuthSigner
from app.integrations.upbit.client import UpbitRestClient


def test_rest_client_attaches_bearer_header_and_query_hash() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")
    client = UpbitRestClient(
        base_url="https://api.upbit.com",
        auth_signer=signer,
        transport=transport,
    )

    response = client.get("/v1/orders/open", params={"market": "KRW-XRP"})

    assert response == {"ok": True}
    assert captured["url"] == "https://api.upbit.com/v1/orders/open?market=KRW-XRP"
    assert str(captured["authorization"]).startswith("Bearer ")


def test_rest_client_preserves_list_json_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"uuid": "1"}])

    transport = httpx.MockTransport(handler)
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")
    client = UpbitRestClient(
        base_url="https://api.upbit.com",
        auth_signer=signer,
        transport=transport,
    )

    response = client.get("/v1/accounts")

    assert response == [{"uuid": "1"}]


def test_rest_client_posts_order_test_payload_with_auth_header() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["json"] = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    signer = UpbitAuthSigner(access_key="access", secret_key="secret")
    client = UpbitRestClient(
        base_url="https://api.upbit.com",
        auth_signer=signer,
        transport=transport,
    )

    response = client.post(
        "/v1/orders/test",
        json_payload={
            "market": "KRW-XRP",
            "side": "bid",
            "price": "820",
            "volume": "120.5",
            "ord_type": "limit",
        },
    )

    assert response == {"ok": True}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.upbit.com/v1/orders/test"
    assert str(captured["authorization"]).startswith("Bearer ")
    assert '"market":"KRW-XRP"' in str(captured["json"])
