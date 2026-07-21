from pathlib import Path

from app.services.market.etf_alert import EtfContextChangeMonitor


class NotifierStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify_etf_context_changed(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _context(*, aum: float = 1_060_430_000.0, state: str = "neutral") -> dict[str, object]:
    return {
        "etf": {
            "state": state,
            "flow_usd": 0.0,
            "flow_date": "2026-07-18",
            "total_aum_usd": aum,
            "total_holding_coin": 970_900_000.0,
            "daily_volume_usd": 9_190_000.0,
            "data_status": "fresh",
        }
    }


def test_etf_context_monitor_baselines_then_notifies_meaningful_change(tmp_path: Path) -> None:
    notifier = NotifierStub()
    monitor = EtfContextChangeMonitor(state_path=tmp_path / "etf.json", notifier=notifier)

    assert monitor.observe(market="KRW-XRP", mode="demo", context=_context()) is False
    assert monitor.observe(market="KRW-XRP", mode="demo", context=_context(aum=1_070_000_000.0)) is False
    assert monitor.observe(market="KRW-XRP", mode="demo", context=_context(state="inflow")) is True

    assert len(notifier.calls) == 1
    assert "state" in notifier.calls[0]["changed_fields"]


def test_etf_context_monitor_ignores_flow_date_and_intraday_volume_only_changes(tmp_path: Path) -> None:
    notifier = NotifierStub()
    monitor = EtfContextChangeMonitor(state_path=tmp_path / "etf.json", notifier=notifier)

    assert monitor.observe(market="KRW-XRP", mode="demo", context=_context()) is False
    changed = _context()
    changed["etf"]["flow_date"] = "2026-07-19"
    changed["etf"]["daily_volume_usd"] = 12_000_000.0

    assert monitor.observe(market="KRW-XRP", mode="demo", context=changed) is False
    assert notifier.calls == []
