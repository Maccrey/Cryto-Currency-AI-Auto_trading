from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.runtime.uptime import TradingUptimeStore


def test_trading_uptime_store_accumulates_across_restart(tmp_path) -> None:
    current = datetime(2026, 5, 20, 8, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    def clock() -> datetime:
        return current

    store = TradingUptimeStore(path=tmp_path / "trading-uptime.json", clock=clock)

    store.start()
    current = current + timedelta(seconds=30)
    assert store.uptime_sec() == 30

    restarted_store = TradingUptimeStore(path=tmp_path / "trading-uptime.json", clock=clock)
    current = current + timedelta(seconds=45)
    assert restarted_store.uptime_sec() == 75

    restarted_store.stop()
    current = current + timedelta(seconds=10)
    restarted_store.start()
    current = current + timedelta(seconds=15)
    assert restarted_store.uptime_sec() == 90


def test_trading_uptime_store_resets_only_when_requested(tmp_path) -> None:
    current = datetime(2026, 5, 20, 8, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    store = TradingUptimeStore(path=tmp_path / "trading-uptime.json", clock=lambda: current)

    store.start()
    store.reset()

    assert store.uptime_sec() == 0
    assert not (tmp_path / "trading-uptime.json").exists()
