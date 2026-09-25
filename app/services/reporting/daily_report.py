"""Daily trading report service.

매일 오전 08:00 KST에 지난 24시간의 매매 현황을 텔레그램으로 전송합니다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.reporting.daily_goal import calculate_daily_goal_progress, progress_bar

logger = logging.getLogger(__name__)

# 한국 표준시 UTC+9
KST = timezone(timedelta(hours=9))


class DailyReportService:
    """매일 오전 8시 KST에 24시간 매매 현황을 텔레그램으로 리포팅합니다."""

    def __init__(
        self,
        *,
        execution_ledger: Any,
        telegram_gateway: Any,
        market: str,
        trading_mode: str,
        report_hour_kst: int = 8,
        portfolio_state_provider: Any | None = None,
        initial_capital_provider: Any | None = None,
    ) -> None:
        self._ledger = execution_ledger
        self._gateway = telegram_gateway
        self._market = market
        self._trading_mode = trading_mode
        self._report_hour_kst = report_hour_kst
        self._portfolio_state_provider = portfolio_state_provider
        self._initial_capital_provider = initial_capital_provider
        self._task: asyncio.Task[None] | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """백그라운드 스케줄러 태스크를 시작합니다."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._scheduler_loop(), name="daily_report_scheduler")
        logger.info("daily_report_scheduler_started", extra={"report_hour_kst": self._report_hour_kst})

    def stop(self) -> None:
        """백그라운드 스케줄러 태스크를 중지합니다."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("daily_report_scheduler_stopped")

    # ──────────────────────────────────────────────────────────────────────
    # Scheduling
    # ──────────────────────────────────────────────────────────────────────

    async def _scheduler_loop(self) -> None:
        """매일 오전 report_hour_kst 시에 리포트를 전송합니다."""
        while True:
            try:
                sleep_sec = self._seconds_until_next_report()
                logger.info(
                    "daily_report_next_scheduled",
                    extra={"sleep_sec": round(sleep_sec), "report_hour_kst": self._report_hour_kst},
                )
                await asyncio.sleep(sleep_sec)
                await self._send_report()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("daily_report_scheduler_error")
                await asyncio.sleep(60)  # 오류 시 1분 후 재시도

    def _seconds_until_next_report(self) -> float:
        """다음 오전 8시 KST까지 남은 초를 반환합니다."""
        now_kst = datetime.now(KST)
        target = now_kst.replace(
            hour=self._report_hour_kst,
            minute=0,
            second=0,
            microsecond=0,
        )
        if now_kst >= target:
            target += timedelta(days=1)
        return (target - now_kst).total_seconds()

    # ──────────────────────────────────────────────────────────────────────
    # Report Generation
    # ──────────────────────────────────────────────────────────────────────

    async def _send_report(self) -> None:
        """24시간 매매 현황 리포트를 텔레그램으로 전송합니다."""
        try:
            message = self._build_report_message()
            self._gateway.send_message(message)
            logger.info("daily_report_sent")
        except Exception:
            logger.exception("daily_report_send_failed")

    def _build_report_message(self) -> str:
        """24시간 매매 현황 메시지를 생성합니다."""
        now_kst = datetime.now(KST)
        since_kst = now_kst - timedelta(hours=24)

        # 레저에서 전체 레코드 가져오기
        all_records = self._ledger.list_records()

        # 최근 24시간 레코드만 필터링
        records_24h = self._filter_recent_records(all_records, since=since_kst)

        # 전체 누적 통계 (처음부터 현재까지)
        total_stats = self._compute_stats(all_records)

        # 24시간 통계
        stats_24h = self._compute_stats(records_24h)
        daily_goal = calculate_daily_goal_progress(
            all_records,
            initial_capital=self._get_initial_capital(),
            now=now_kst,
        )
        stats_24h["realized_pnl"] = daily_goal["realized_pnl"]
        stats_24h["stop_loss_pnl"] = daily_goal["stop_loss_pnl"]
        stats_24h["regular_sell_pnl"] = daily_goal["regular_sell_pnl"]
        stats_24h["stop_loss_count"] = daily_goal["stop_loss_count"]
        stats_24h["regular_sell_count"] = daily_goal["regular_sell_count"]
        stats_24h["sell_count"] = daily_goal["sell_count"]
        stats_24h["win_count"] = daily_goal["win_count"]
        stats_24h["loss_count"] = daily_goal["loss_count"]

        # 현재 포트폴리오 상태
        portfolio_info = self._get_portfolio_info()

        mode_label = "데모" if self._trading_mode == "demo" else "실거래"

        lines = [
            "📊 자동매매 일일 리포트",
            "━━━━━━━━━━━━━━━━━━",
            f"🕒 기준: 최근 24시간 · {now_kst.strftime('%m-%d %H:%M')} KST",
            f"💱 시장: {self._market}  |  모드: {mode_label}",
            "",
            "🎯 일일 목표 진행",
        ]
        if daily_goal["available"]:
            goal_pct = float(daily_goal["target_return_rate"]) * 100
            achieved_pct = float(daily_goal["return_rate"]) * 100
            progress_pct = float(daily_goal["progress_pct"])
            progress_label = f"{progress_pct:.1f}%" if progress_pct >= 0 else f"−{abs(progress_pct):.1f}%"
            lines.extend([
                f"목표  +{goal_pct:.2f}%  ({float(daily_goal['target_profit']):,.0f}원)",
                f"진행  {progress_bar(progress_pct)}  {progress_label}",
                f"실현  {achieved_pct:+.3f}%  |  {self._format_pnl(float(daily_goal['realized_pnl']))}",
                f"남은 목표 금액: {float(daily_goal['remaining_profit']):,.0f}원" if not daily_goal["goal_reached"] else "✅ 일일 목표를 달성했습니다.",
            ])
        else:
            lines.append("기준 투자금이 없어 목표 달성률을 계산할 수 없습니다.")
        lines.extend([
            "",
            "📈 체결 현황",
            f"매수 {stats_24h['buy_count']}회  ·  매도 {stats_24h['sell_count']}회  ·  손절 {stats_24h['stop_loss_count']}회",
            f"실현 손익: {self._format_pnl(stats_24h['realized_pnl'])}",
        ])

        # 24시간 손절 세부사항
        if stats_24h["stop_loss_count"] > 0:
            lines.append(f"손절 손익: {self._format_pnl(stats_24h['stop_loss_pnl'])}")
        if stats_24h["regular_sell_count"] > 0:
            lines.append(f"일반 매도 손익: {self._format_pnl(stats_24h['regular_sell_pnl'])}")

        # 수익/손실 거래 비율
        if stats_24h["sell_count"] > 0:
            win_rate = stats_24h["win_count"] / stats_24h["sell_count"] * 100
            lines.append(f"승률: {win_rate:.1f}%  ({stats_24h['win_count']}승 {stats_24h['loss_count']}패)")

        # 최대 단일 손익
        if stats_24h["max_single_profit"] is not None:
            lines.append(f"최대 단건 수익: {self._format_pnl(stats_24h['max_single_profit'])}")
        if stats_24h["max_single_loss"] is not None:
            lines.append(f"최대 단건 손실: {self._format_pnl(stats_24h['max_single_loss'])}")

        lines.extend(["", "📚 누적 기록"])
        lines.append(f"총 매수 {total_stats['buy_count']}회  ·  매도 {total_stats['sell_count']}회  ·  손절 {total_stats['stop_loss_count']}회")
        lines.append(f"누적 실현 손익: {self._format_pnl(total_stats['realized_pnl'])}")

        if total_stats["sell_count"] > 0:
            total_win_rate = total_stats["win_count"] / total_stats["sell_count"] * 100
            lines.append(f"전체 승률: {total_win_rate:.1f}%")

        # 포트폴리오 현황
        if portfolio_info:
            lines.append("")
            lines.append("[ 현재 포트폴리오 ]")
            lines.extend(portfolio_info)

        # 24시간 거래 없음 안내
        if stats_24h["buy_count"] == 0 and stats_24h["sell_count"] == 0:
            lines.append("")
            lines.append("⚠️ 최근 24시간 동안 체결된 매매가 없습니다. 목표는 실현 손익 기준으로 집계됩니다.")

        lines.append("━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    def _get_initial_capital(self) -> float:
        if self._initial_capital_provider is not None:
            try:
                return max(float(self._initial_capital_provider() or 0.0), 0.0)
            except Exception:
                logger.exception("daily_report_initial_capital_unavailable")
        if self._portfolio_state_provider is not None:
            try:
                state = self._portfolio_state_provider()
                if state is not None:
                    return max(float(getattr(state, "cash_balance", 0.0) or 0.0), 0.0)
            except Exception:
                logger.exception("daily_report_portfolio_state_unavailable")
        return 0.0

    # ──────────────────────────────────────────────────────────────────────
    # Statistics Helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _filter_recent_records(records: list[Any], *, since: datetime) -> list[Any]:
        """since 이후의 레코드만 반환합니다."""
        result = []
        for record in records:
            recorded_at = record.recorded_at
            if recorded_at is None:
                continue
            try:
                if isinstance(recorded_at, str):
                    ts = datetime.fromisoformat(recorded_at)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=KST)
                else:
                    ts = recorded_at
                if ts >= since:
                    result.append(record)
            except (ValueError, TypeError):
                continue
        return result

    @staticmethod
    def _compute_stats(records: list[Any]) -> dict[str, Any]:
        """레코드 목록에서 매매 통계를 계산합니다."""
        buy_count = 0
        sell_count = 0
        stop_loss_count = 0
        regular_sell_count = 0
        win_count = 0
        loss_count = 0
        realized_pnl = 0.0
        stop_loss_pnl = 0.0
        regular_sell_pnl = 0.0
        max_single_profit: float | None = None
        max_single_loss: float | None = None
        open_quantity = 0.0
        average_cost = 0.0

        for record in records:
            fill = record.fill
            if fill.status != "filled":
                continue

            if fill.side == "buy":
                buy_count += 1
                total_cost = (
                    (average_cost * open_quantity)
                    + (fill.filled_price * fill.filled_quantity)
                    + fill.fee
                )
                open_quantity += fill.filled_quantity
                average_cost = 0.0 if open_quantity <= 0 else total_cost / open_quantity
                continue

            sell_count += 1
            if fill.is_stop_loss:
                stop_loss_count += 1
            else:
                regular_sell_count += 1

            matched_qty = min(open_quantity, fill.filled_quantity)
            if matched_qty > 0:
                proceeds = (fill.filled_price * matched_qty) - fill.fee
                pnl = proceeds - (average_cost * matched_qty)
                realized_pnl += pnl
                if fill.is_stop_loss:
                    stop_loss_pnl += pnl
                else:
                    regular_sell_pnl += pnl

                if pnl > 0:
                    win_count += 1
                    max_single_profit = pnl if max_single_profit is None else max(max_single_profit, pnl)
                else:
                    loss_count += 1
                    max_single_loss = pnl if max_single_loss is None else min(max_single_loss, pnl)

                open_quantity = round(open_quantity - matched_qty, 8)
                if open_quantity <= 0:
                    open_quantity = 0.0
                    average_cost = 0.0

        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "stop_loss_count": stop_loss_count,
            "regular_sell_count": regular_sell_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "realized_pnl": round(realized_pnl, 2),
            "stop_loss_pnl": round(stop_loss_pnl, 2),
            "regular_sell_pnl": round(regular_sell_pnl, 2),
            "max_single_profit": None if max_single_profit is None else round(max_single_profit, 2),
            "max_single_loss": None if max_single_loss is None else round(max_single_loss, 2),
        }

    def _get_portfolio_info(self) -> list[str]:
        """현재 포트폴리오 상태 정보를 반환합니다."""
        if self._portfolio_state_provider is None:
            return []
        try:
            state = self._portfolio_state_provider()
            if state is None:
                return []
            lines = []
            if hasattr(state, "cash_balance"):
                lines.append(f"  현금 잔고: {state.cash_balance:,.0f}원")
            if hasattr(state, "asset_balance") and state.asset_balance > 0:
                coin = self._market.replace("KRW-", "")
                lines.append(f"  {coin} 보유: {state.asset_balance:,.8f}개")
                if hasattr(state, "avg_buy_price") and state.avg_buy_price > 0:
                    lines.append(f"  평균 매수가: {state.avg_buy_price:,.2f}원")
            return lines
        except Exception:
            return []

    @staticmethod
    def _format_pnl(value: float) -> str:
        """손익 금액을 부호와 함께 포맷합니다."""
        if value > 0:
            return f"▲ +{value:,.2f}원 (수익)"
        if value < 0:
            return f"▼ {value:,.2f}원 (손실)"
        return f"0원 (보합)"
