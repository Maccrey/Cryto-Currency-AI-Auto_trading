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

        active_position = "none"
        if position is not None:
            active_position = (
                f"{position.quantity}@{position.entry_price} "
                f"stop={position.stop_loss_price}"
            )

        return "\n".join(
            [
                "[CURRENT_TRADING_REPORT]",
                f"reported_at={reported_at.isoformat()}",
                f"market={context.market}",
                f"mode={context.trading_mode}",
                f"learning_enabled={context.learning_enabled}",
                f"current_price={None if latest_price is None else latest_price.price}",
                f"price_recorded_at={None if latest_price is None else latest_price.recorded_at}",
                f"cash_balance={None if portfolio is None else portfolio.cash_balance}",
                f"asset_balance={None if portfolio is None else portfolio.asset_balance}",
                f"realized_pnl={summary.realized_pnl}",
                f"buy_count={summary.buy_count}",
                f"sell_count={summary.sell_count}",
                f"stop_loss_count={summary.stop_loss_count}",
                f"recent_stop_loss_reason={summary.recent_stop_loss_reason}",
                f"active_position={active_position}",
                f"safe_mode={context.boot_state.safe_mode}",
                f"hard_stop={context.boot_state.hard_stop}",
                f"trading_ready={context.boot_state.trading_ready}",
                f"last_learning_event={last_learning_event}",
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
                "[DAILY_TRADING_REPORT]",
                f"reported_at={reported_at.isoformat()}",
                f"target_date={target_date.isoformat()}",
                f"market={context.market}",
                f"mode={context.trading_mode}",
                f"total_learning_events={len(daily_events)}",
                f"signals={len(signal_events)}",
                f"blocked_signals={blocked_signals}",
                f"fills={event_counts.get('fill_result', 0)}",
                f"positions_opened={event_counts.get('position_opened', 0)}",
                f"positions_exited={event_counts.get('position_exit_completed', 0)}",
                f"position_updates={event_counts.get('position_lifecycle_updated', 0)}",
                f"promotion_reviews={event_counts.get('promotion_review_completed', 0)}",
                f"recovery_events={event_counts.get('restart_detected', 0) + event_counts.get('recovery_completed', 0)}",
                f"learning_updates={learning_updates}",
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
