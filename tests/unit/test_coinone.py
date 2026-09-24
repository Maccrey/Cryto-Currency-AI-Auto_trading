import base64
import hashlib
import hmac
import json
from uuid import UUID

import httpx
import pytest

from app.integrations.coinone.client import CoinoneAPIError, CoinoneRestClient
from app.integrations.coinone.gateway import CoinoneLiveOrderGateway
from app.integrations.coinone.market import CoinoneMarketProvider
from app.services.config.env_file import EnvFileService
from app.services.portfolio.sync import PortfolioSyncService
from app.services.recovery.open_orders import OpenOrderReconciler


def test_signed_private_requests_and_account_mapping():
    nonces = []
    def handler(request):
        encoded = request.headers["x-coinone-payload"].encode()
        assert request.content == encoded
        assert request.headers["x-coinone-signature"] == hmac.new(b"secret", encoded, hashlib.sha512).hexdigest()
        payload = json.loads(base64.b64decode(encoded))
        assert payload["access_token"] == "token"
        assert UUID(payload["nonce"]).version == 4
        nonces.append(payload["nonce"])
        if request.url.path.endswith("balance/all"):
            data = {"balances": [
                {"currency": "KRW", "available": "10000", "limit": "2000", "average_price": "1"},
                {"currency": "XRP", "available": "3", "limit": "2", "average_price": "2000"}]}
        else:
            assert payload["target_currency"] == "XRP"
            data = {"active_orders": [{"order_id": "open-1"}]}
        return httpx.Response(200, json={"result": "success", "error_code": "0", **data})
    client = CoinoneRestClient(access_token="token", secret_key="secret", transport=httpx.MockTransport(handler))
    portfolio = PortfolioSyncService(client, "XRP").sync()
    assert (portfolio.cash_balance, portfolio.asset_balance, portfolio.avg_buy_price) == (10000, 3, 2000)
    assert OpenOrderReconciler(upbit_client=client, trade_market="KRW-XRP").reconcile()["order_ids"] == ["open-1"]
    assert len(set(nonces)) == 2


def test_api_error_does_not_expose_credentials():
    client = CoinoneRestClient(access_token="secret-token", secret_key="secret", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"result": "error", "error_code": "103", "message": "secret-token"})))
    with pytest.raises(CoinoneAPIError, match="103") as error:
        client.post("/v2.1/account/balance/all")
    assert "secret-token" not in str(error.value)


def test_market_buy_sell_and_partial_cancel_mapping():
    bodies = []
    def handler(request):
        payload = json.loads(base64.b64decode(request.content))
        bodies.append(payload)
        data = {"order_id": "id-1"}
        if request.url.path.endswith("detail"):
            data = {"order": {"order_id": "id-1", "status": "CANCELED_LIMIT_PRICE_EXCEED", "side": "SELL",
                              "average_executed_price": "2100", "executed_qty": "2", "fee": "8.4"}}
        return httpx.Response(200, json={"result": "success", "error_code": "0", **data})
    client = CoinoneRestClient(access_token="token", secret_key="secret", transport=httpx.MockTransport(handler))
    gateway = CoinoneLiveOrderGateway(rest_client=client, market="KRW-XRP")
    gateway.place_order(market="KRW-XRP", side="buy", price=2000, quantity=3.25, order_type="market")
    gateway.place_order(market="KRW-XRP", side="sell", price=2000, quantity=3.25, order_type="market")
    assert bodies[0]["amount"] == "6500.0000" and "qty" not in bodies[0]
    assert bodies[1]["qty"] == "3.25" and "amount" not in bodies[1]
    status = gateway.get_order(order_id="id-1")
    assert status["state"] == "cancel" and status["executed_volume"] == "2"
    assert status["average_price"] == "2100"


def test_public_prices_and_candles_use_coinone():
    def handler(request):
        assert request.url.host == "api.coinone.co.kr"
        assert "x-coinone-payload" not in request.headers
        if "ticker_new" in request.url.path:
            data = {"tickers": [{"last": "2100", "first": "2000", "target_volume": "100", "quote_volume": "210000"}]}
        else:
            data = {"chart": [{"timestamp": 1700000000000, "close": "2100", "open": "2000", "high": "2200", "low": "1900", "target_volume": "100", "quote_volume": "210000"}]}
        return httpx.Response(200, json={"result": "success", "error_code": "0", **data})
    provider = CoinoneMarketProvider(transport=httpx.MockTransport(handler))
    assert provider.get_current_snapshot("KRW-XRP").signed_change_rate == pytest.approx(.05)
    assert provider.fetch_recent(market="KRW-XRP", count=72)[0].trade_price == 2100


def test_exchange_specific_keys_are_preserved_masked_and_required(tmp_path):
    service = EnvFileService(tmp_path / ".env")
    missing = service.save({"TRADING_MODE": "live", "LIVE_EXCHANGE": "coinone"})
    assert missing["missing_for_live"] == ["COINONE_ACCESS_TOKEN", "COINONE_SECRET_KEY"]
    result = service.save({"TRADING_MODE": "live", "LIVE_EXCHANGE": "coinone", "COINONE_ACCESS_TOKEN": "token", "COINONE_SECRET_KEY": "secret"})
    assert result["saved"]
    current = service.current()
    assert current["values"]["COINONE_ACCESS_TOKEN"] == "***"
    assert service.save({"COINONE_ACCESS_TOKEN": "***", "COINONE_SECRET_KEY": "***"})["saved"]
    assert not service.save({"LIVE_EXCHANGE": "invalid"})["saved"]
    assert service.save({"LIVE_EXCHANGE": "upbit"})["missing_for_live"] == ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY"]
