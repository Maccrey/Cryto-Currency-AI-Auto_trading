from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.portfolio.sync import PortfolioState
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState
from app.services.reporting.telegram import (
    TelegramTradingReportScheduler,
    TelegramTradingReportService,
    TradingReportContext,
)


class StubTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


def _build_report_service(tmp_path: Path) -> tuple[TelegramTradingReportService, StubTelegramGateway]:
    gateway = StubTelegramGateway()
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"blocked": True},
                recorded_at="2026-04-28T10:00:00+09:00",
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"side": "buy"},
                recorded_at="2026-04-28T10:01:00+09:00",
            ),
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={"signal_level": "strong"},
                recorded_at="2026-04-28T10:02:00+09:00",
            ),
            LearningEvent(
                event_name="position_exit_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"reason_code": "STOP_LOSS_PRICE_HIT"},
                recorded_at="2026-04-28T11:00:00+09:00",
            ),
            LearningEvent(
                event_name="promotion_review_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"evaluation_status": "not_ready"},
                recorded_at="2026-04-28T12:00:00+09:00",
            ),
        ],
    )
    execution_ledger = ExecutionLedger()
    execution_ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=10.0,
            fee=3.41,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    market_price_store = MarketPriceStore(
        timestamp_provider=lambda: "2026-04-29T06:00:00+09:00",
    )
    market_price_store.save(market="KRW-XRP", price=835.0)

    service = TelegramTradingReportService(
        gateway=gateway,
        context=TradingReportContext(
            market="KRW-XRP",
            trading_mode="demo",
            learning_enabled=True,
            boot_state=BootState(
                safe_mode=False,
                hard_stop=False,
                trading_ready=True,
                failure_stage=None,
                portfolio_state=PortfolioState(
                    cash_balance=1000000.0,
                    asset_currency="XRP",
                    asset_balance=0.0,
                    avg_buy_price=0.0,
                ),
                reconcile_result=None,
            ),
            execution_ledger=execution_ledger,
            learning_service=learning_service,
            market_price_store=market_price_store,
            position_store=CurrentPositionStore(),
        ),
    )
    return service, gateway


def test_telegram_report_service_sends_current_trading_report(tmp_path: Path) -> None:
    service, gateway = _build_report_service(tmp_path)

    message = service.send_current_report(
        reported_at=datetime(2026, 4, 29, 7, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert gateway.messages == [message]
    assert "현재 거래 상태 보고입니다." in message
    assert "현재가는 835.00원입니다." in message
    assert "현금 잔고는 1,000,000.00원" in message
    assert "매수는 1번" in message
    assert "거래 가능 상태는 정상" in message


def test_telegram_report_service_sends_daily_learning_report(tmp_path: Path) -> None:
    service, gateway = _build_report_service(tmp_path)

    message = service.send_daily_report(
        reported_at=datetime(2026, 4, 29, 6, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        target_date=datetime(2026, 4, 28, tzinfo=ZoneInfo("Asia/Seoul")).date(),
    )

    assert gateway.messages == [message]
    assert "어제 거래 학습 보고입니다." in message
    assert "2026-04-28 기준 보고" in message
    assert "학습 이벤트는 총 5건" in message
    assert "매매 신호는 1건 발생했고 그중 1건은 차단" in message
    assert "체결은 1건, 포지션 진입은 1건, 포지션 종료는 1건" in message
    assert "승격 검토는 1건" in message
    assert "학습 반영 항목은 signal_features,execution_results,position_outcomes,promotion_quality" in message


def test_telegram_report_scheduler_sends_without_duplicates(tmp_path: Path) -> None:
    service, gateway = _build_report_service(tmp_path)
    scheduler = TelegramTradingReportScheduler(report_service=service)
    six_am = datetime(2026, 4, 29, 6, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    assert scheduler.tick(six_am) == ["current", "daily"]
    assert scheduler.tick(six_am) == []
    assert scheduler.tick(six_am.replace(minute=1)) == []
    assert scheduler.tick(six_am.replace(hour=7)) == ["current"]
    assert scheduler.tick(six_am.replace(hour=5)) == []

    assert len(gateway.messages) == 3
