"""Unit tests for DailyReportService."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.reporting.daily_report import DailyReportService

KST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_fill(
    side: str,
    filled_price: float,
    filled_quantity: float,
    fee: float = 0.0,
    is_stop_loss: bool = False,
    status: str = "filled",
    mode: str = "demo",
) -> Any:
    fill = MagicMock()
    fill.side = side
    fill.filled_price = filled_price
    fill.filled_quantity = filled_quantity
    fill.fee = fee
    fill.is_stop_loss = is_stop_loss
    fill.status = status
    fill.mode = mode
    fill.market = "KRW-XRP"
    return fill


def _make_record(fill: Any, recorded_at: datetime | None = None) -> Any:
    record = MagicMock()
    record.fill = fill
    record.recorded_at = recorded_at.isoformat() if recorded_at else None
    return record


def _build_service(
    records: list[Any] | None = None,
    gateway: Any | None = None,
    portfolio_provider: Any | None = None,
) -> DailyReportService:
    ledger = MagicMock()
    ledger.list_records.return_value = records or []
    gw = gateway or MagicMock()
    return DailyReportService(
        execution_ledger=ledger,
        telegram_gateway=gw,
        market="KRW-XRP",
        trading_mode="demo",
        report_hour_kst=8,
        portfolio_state_provider=portfolio_provider,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _filter_recent_records
# ──────────────────────────────────────────────────────────────────────────────

def test_filter_recent_records_includes_records_within_24h() -> None:
    now = datetime.now(KST)
    recent = _make_record(_make_fill("buy", 1000.0, 100.0), recorded_at=now - timedelta(hours=12))
    old = _make_record(_make_fill("buy", 1000.0, 100.0), recorded_at=now - timedelta(hours=25))
    since = now - timedelta(hours=24)
    result = DailyReportService._filter_recent_records([recent, old], since=since)
    assert len(result) == 1
    assert result[0] is recent


def test_filter_recent_records_excludes_none_recorded_at() -> None:
    record = _make_record(_make_fill("buy", 1000.0, 100.0), recorded_at=None)
    since = datetime.now(KST) - timedelta(hours=24)
    result = DailyReportService._filter_recent_records([record], since=since)
    assert result == []


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _compute_stats
# ──────────────────────────────────────────────────────────────────────────────

def test_compute_stats_empty_records() -> None:
    stats = DailyReportService._compute_stats([])
    assert stats["buy_count"] == 0
    assert stats["sell_count"] == 0
    assert stats["realized_pnl"] == 0.0


def test_compute_stats_single_buy_sell_profit() -> None:
    buy = _make_record(_make_fill("buy", 1000.0, 100.0, fee=50.0))
    sell = _make_record(_make_fill("sell", 1050.0, 100.0, fee=52.5))
    stats = DailyReportService._compute_stats([buy, sell])
    assert stats["buy_count"] == 1
    assert stats["sell_count"] == 1
    assert stats["win_count"] == 1
    assert stats["loss_count"] == 0
    assert stats["realized_pnl"] > 0


def test_compute_stats_stop_loss_sell() -> None:
    buy = _make_record(_make_fill("buy", 1000.0, 100.0, fee=50.0))
    sell = _make_record(_make_fill("sell", 970.0, 100.0, fee=48.5, is_stop_loss=True))
    stats = DailyReportService._compute_stats([buy, sell])
    assert stats["stop_loss_count"] == 1
    assert stats["realized_pnl"] < 0
    assert stats["stop_loss_pnl"] < 0


def test_compute_stats_skips_non_filled_records() -> None:
    fill = _make_fill("buy", 1000.0, 100.0, status="pending")
    record = _make_record(fill)
    stats = DailyReportService._compute_stats([record])
    assert stats["buy_count"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _format_pnl
# ──────────────────────────────────────────────────────────────────────────────

def test_format_pnl_positive() -> None:
    result = DailyReportService._format_pnl(12345.67)
    assert "▲" in result
    assert "수익" in result


def test_format_pnl_negative() -> None:
    result = DailyReportService._format_pnl(-9876.54)
    assert "▼" in result
    assert "손실" in result


def test_format_pnl_zero() -> None:
    result = DailyReportService._format_pnl(0.0)
    assert "보합" in result


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _build_report_message
# ──────────────────────────────────────────────────────────────────────────────

def test_build_report_message_no_trades() -> None:
    svc = _build_service(records=[])
    msg = svc._build_report_message()
    assert "24시간" in msg
    assert "체결된 매매가 없습니다" in msg


def test_build_report_message_with_trades() -> None:
    now = datetime.now(KST)
    buy = _make_record(_make_fill("buy", 1600.0, 1000.0, fee=0.8), recorded_at=now - timedelta(hours=6))
    sell = _make_record(_make_fill("sell", 1620.0, 1000.0, fee=0.81), recorded_at=now - timedelta(hours=5))
    svc = _build_service(records=[buy, sell])
    msg = svc._build_report_message()
    assert "매수 횟수: 1회" in msg
    assert "매도 횟수: 1회" in msg
    assert "실현 손익" in msg


def test_build_report_message_includes_market_and_mode() -> None:
    svc = _build_service(records=[])
    msg = svc._build_report_message()
    assert "KRW-XRP" in msg
    assert "데모" in msg


def test_build_report_message_includes_portfolio_when_provider_set() -> None:
    portfolio = MagicMock()
    portfolio.cash_balance = 500000.0
    portfolio.asset_balance = 1234.5
    portfolio.avg_buy_price = 1600.0
    svc = _build_service(records=[], portfolio_provider=lambda: portfolio)
    msg = svc._build_report_message()
    assert "현금 잔고" in msg
    assert "500,000" in msg


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _seconds_until_next_report
# ──────────────────────────────────────────────────────────────────────────────

def test_seconds_until_next_report_future_same_day() -> None:
    """현재가 7시일 때 8시까지 약 1시간 남음."""
    svc = _build_service()
    now_kst = datetime(2026, 6, 26, 7, 0, 0, tzinfo=KST)
    with patch("app.services.reporting.daily_report.datetime") as mock_dt:
        mock_dt.now.return_value = now_kst
        mock_dt.fromisoformat = datetime.fromisoformat
        secs = svc._seconds_until_next_report()
    assert 3500 < secs < 3700  # 약 1시간


def test_seconds_until_next_report_past_today() -> None:
    """현재가 9시일 때 다음날 8시까지 약 23시간 남음."""
    svc = _build_service()
    now_kst = datetime(2026, 6, 26, 9, 0, 0, tzinfo=KST)
    with patch("app.services.reporting.daily_report.datetime") as mock_dt:
        mock_dt.now.return_value = now_kst
        mock_dt.fromisoformat = datetime.fromisoformat
        secs = svc._seconds_until_next_report()
    assert 82700 < secs < 82900  # 약 23시간


# ──────────────────────────────────────────────────────────────────────────────
# Tests: start / stop lifecycle
# ──────────────────────────────────────────────────────────────────────────────

def test_daily_report_service_start_creates_task() -> None:
    import asyncio

    async def _run() -> None:
        svc = _build_service()
        svc.start()
        assert svc._task is not None
        assert not svc._task.done()
        svc.stop()

    asyncio.run(_run())


def test_daily_report_service_stop_cancels_task() -> None:
    import asyncio

    async def _run() -> None:
        svc = _build_service()
        svc.start()
        svc.stop()
        await asyncio.sleep(0)  # 태스크 취소 처리 대기
        assert svc._task is None or svc._task.cancelled() or svc._task.done()

    asyncio.run(_run())
