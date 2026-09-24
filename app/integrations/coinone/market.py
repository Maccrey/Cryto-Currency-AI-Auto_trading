from datetime import UTC, datetime

from app.integrations.coinone.client import CoinoneRestClient
from app.services.market.bootstrap import UpbitCandleSnapshot
from app.services.market.upbit_ticker import UpbitTickerSnapshot


class CoinoneMarketProvider:
    def __init__(self, *, base_url="https://api.coinone.co.kr", transport=None):
        self._client = CoinoneRestClient(base_url=base_url, transport=transport)

    def get_current_snapshot(self, market):
        quote, coin = market.split("-")
        row = self._client.public_get(f"/public/v2/ticker_new/{quote}/{coin}")["tickers"][0]
        price, first = float(row["last"]), float(row["first"])
        return UpbitTickerSnapshot(trade_price=price,
            signed_change_rate=price / first - 1 if first > 0 else None,
            acc_trade_volume_24h=float(row["target_volume"]),
            acc_trade_price_24h=float(row["quote_volume"]))

    def get_current_price(self, market):
        return self.get_current_snapshot(market).trade_price

    def fetch_recent(self, *, market, count):
        quote, coin = market.split("-")
        rows = self._client.public_get(f"/public/v2/chart/{quote}/{coin}",
                                     params={"interval": "1h", "size": min(count, 500)})["chart"]
        return sorted([UpbitCandleSnapshot(market=market, trade_price=float(row["close"]),
            recorded_at=datetime.fromtimestamp(row["timestamp"] / 1000, UTC).isoformat(),
            opening_price=float(row["open"]), high_price=float(row["high"]), low_price=float(row["low"]),
            candle_acc_trade_volume=float(row["target_volume"]), candle_acc_trade_price=float(row["quote_volume"]))
            for row in rows], key=lambda row: row.recorded_at)

    def close(self):
        self._client.close()
