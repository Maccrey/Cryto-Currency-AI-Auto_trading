from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradingReportContext:
    market: str
    trading_mode: str
    learning_enabled: bool
    boot_state: BootState
    execution_ledger: ExecutionLedger
    learning_service: LearningService
    market_price_store: MarketPriceStore
    position_store: CurrentPositionStore


class TelegramTradingReportService:
    """Build and send scheduled trading reports."""

    def __init__(
        self,
        *,
        gateway: Any,
        context: TradingReportContext,
    ) -> None:
        self._gateway = gateway
        self._context = context

    def send_current_report(self, *, reported_at: datetime) -> str:
        message = self.build_current_report(reported_at=reported_at)
        self._gateway.send_message(message)
        return message

    def send_daily_report(self, *, reported_at: datetime, target_date: date) -> str:
        message = self.build_daily_report(
            reported_at=reported_at,
            target_date=target_date,
        )
        self._gateway.send_message(message)
        return message

    def build_current_report(self, *, reported_at: datetime) -> str:
        context = self._context
        summary = context.execution_ledger.summarize()
        latest_price = context.market_price_store.get(context.market)
        position = context.position_store.get()
        portfolio = context.boot_state.portfolio_state
        events = context.learning_service.recent_events()
        last_learning_event = None if not events else events[-1].event_name

        active_position = "현재 보유 포지션은 없습니다."
        if position is not None:
            active_position = (
                f"{position.market}를 평균 {position.entry_price:,.2f}원에 "
                f"{position.quantity:,.8f}개 보유 중이며 손절 기준가는 {position.stop_loss_price:,.2f}원입니다."
            )

        return "\n".join(
            [
                "현재 거래 상태 보고입니다.",
                f"보고 시각은 {reported_at.isoformat()}입니다.",
                f"{context.market}를 {context.trading_mode} 모드로 운영 중입니다.",
                f"현재가는 {'확인되지 않았습니다' if latest_price is None else f'{latest_price.price:,.2f}원'}입니다.",
                f"현금 잔고는 {'확인되지 않았습니다' if portfolio is None else f'{portfolio.cash_balance:,.2f}원'}이고 보유 수량은 {'확인되지 않았습니다' if portfolio is None else f'{portfolio.asset_balance:,.8f}개'}입니다.",
                f"현재까지 실현 손익은 {summary.realized_pnl:,.2f}원입니다.",
                f"매수는 {summary.buy_count}번, 매도는 {summary.sell_count}번 체결되었고 손절 매도는 {summary.stop_loss_count}번입니다.",
                active_position,
                f"거래 가능 상태는 {'정상' if context.boot_state.trading_ready else '중지'}이며 안전 모드는 {'켜짐' if context.boot_state.safe_mode else '꺼짐'}입니다.",
                f"최근 학습 이벤트는 {last_learning_event or '없음'}입니다.",
            ],
        )

    def build_daily_report(self, *, reported_at: datetime, target_date: date) -> str:
        context = self._context
        daily_events = [
            event
            for event in context.learning_service.recent_events()
            if self._event_date(event) == target_date
        ]
        event_counts = Counter(event.event_name for event in daily_events)
        signal_events = [
            event for event in daily_events if event.event_name == "signal_generated"
        ]
        blocked_signals = sum(
            1 for event in signal_events if bool(event.payload.get("blocked"))
        )
        learning_updates = self._describe_learning_updates(daily_events)

        return "\n".join(
            [
                "어제 거래 학습 보고입니다.",
                f"{target_date.isoformat()} 기준 보고를 {reported_at.isoformat()}에 보냅니다.",
                f"{context.market}를 {context.trading_mode} 모드로 운영했습니다.",
                f"학습 이벤트는 총 {len(daily_events)}건 기록되었습니다.",
                f"매매 신호는 {len(signal_events)}건 발생했고 그중 {blocked_signals}건은 차단되었습니다.",
                f"체결은 {event_counts.get('fill_result', 0)}건, 포지션 진입은 {event_counts.get('position_opened', 0)}건, 포지션 종료는 {event_counts.get('position_exit_completed', 0)}건입니다.",
                f"포지션 변경은 {event_counts.get('position_lifecycle_updated', 0)}건, 승격 검토는 {event_counts.get('promotion_review_completed', 0)}건, 복구 이벤트는 {event_counts.get('restart_detected', 0) + event_counts.get('recovery_completed', 0)}건입니다.",
                f"학습 반영 항목은 {learning_updates}입니다.",
            ],
        )

    @staticmethod
    def _event_date(event: LearningEvent) -> date | None:
        try:
            return datetime.fromisoformat(
                event.recorded_at.replace("Z", "+00:00"),
            ).date()
        except ValueError:
            return None

    @staticmethod
    def _describe_learning_updates(events: list[LearningEvent]) -> str:
        categories: list[str] = []
        event_names = {event.event_name for event in events}
        if "signal_generated" in event_names:
            categories.append("signal_features")
        if "fill_result" in event_names:
            categories.append("execution_results")
        if "position_opened" in event_names or "position_exit_completed" in event_names:
            categories.append("position_outcomes")
        if "promotion_review_completed" in event_names:
            categories.append("promotion_quality")
        if "restart_detected" in event_names or "recovery_completed" in event_names:
            categories.append("recovery_stability")
        return "none" if not categories else ",".join(categories)


class TelegramTradingReportScheduler:
    """Send current reports hourly from 06:00 to 24:00 and daily reports at 06:00."""

    def __init__(
        self,
        *,
        report_service: TelegramTradingReportService,
        timezone: str = "Asia/Seoul",
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Any] | None = None,
        poll_interval_sec: float = 60.0,
    ) -> None:
        self._report_service = report_service
        self._timezone = ZoneInfo(timezone)
        self._clock = clock or (lambda: datetime.now(self._timezone))
        self._sleep = sleep or asyncio.sleep
        self._poll_interval_sec = poll_interval_sec
        self._task: asyncio.Task[None] | None = None
        self._sent_current_keys: set[str] = set()
        self._sent_daily_keys: set[str] = set()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while True:
            self.tick(self._clock())
            await self._sleep(self._poll_interval_sec)

    def tick(self, now: datetime) -> list[str]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=self._timezone)
        else:
            now = now.astimezone(self._timezone)
        if now.minute != 0:
            return []

        sent: list[str] = []
        if 6 <= now.hour < 24:
            current_key = now.strftime("%Y-%m-%dT%H")
            if current_key not in self._sent_current_keys:
                try:
                    self._report_service.send_current_report(reported_at=now)
                except Exception:
                    logger.exception("telegram_current_report_failed")
                    sent.append("current_failed")
                else:
                    self._sent_current_keys.add(current_key)
                    sent.append("current")

        if now.hour == 6:
            daily_key = now.strftime("%Y-%m-%d")
            if daily_key not in self._sent_daily_keys:
                try:
                    self._report_service.send_daily_report(
                        reported_at=now,
                        target_date=now.date() - timedelta(days=1),
                    )
                except Exception:
                    logger.exception("telegram_daily_report_failed")
                    sent.append("daily_failed")
                else:
                    self._sent_daily_keys.add(daily_key)
                    sent.append("daily")

        return sent
