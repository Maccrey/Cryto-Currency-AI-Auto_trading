from __future__ import annotations

from app.services.portfolio.sync import PortfolioSyncError, PortfolioSyncService


class StubUpbitClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, path: str, *, params=None):
        assert path == "/v1/accounts"
        assert params is None
        return self.payload


def test_portfolio_sync_extracts_cash_and_target_asset() -> None:
    service = PortfolioSyncService(
        upbit_client=StubUpbitClient(
            [
                {"currency": "KRW", "balance": "125000.5", "avg_buy_price": "0"},
                {"currency": "XRP", "balance": "230.0", "avg_buy_price": "820.1"},
                {"currency": "BTC", "balance": "0.01", "avg_buy_price": "100000000"},
            ],
        ),
        trade_coin="XRP",
    )

    state = service.sync()

    assert state.cash_balance == 125000.5
    assert state.asset_currency == "XRP"
    assert state.asset_balance == 230.0
    assert state.avg_buy_price == 820.1


def test_portfolio_sync_fails_when_krw_balance_missing() -> None:
    service = PortfolioSyncService(
        upbit_client=StubUpbitClient(
            [{"currency": "XRP", "balance": "10", "avg_buy_price": "800"}],
        ),
        trade_coin="XRP",
    )

    try:
        service.sync()
    except PortfolioSyncError as exc:
        assert "KRW" in str(exc)
    else:
        raise AssertionError("Portfolio sync should fail without KRW balance")
