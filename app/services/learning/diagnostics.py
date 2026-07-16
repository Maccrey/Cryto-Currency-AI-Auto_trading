from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.learning.jsonl import tail_jsonl_objects
from app.services.market.context import ExternalMarketContextService


class LearningLogDiagnostics:
    """Summarize persisted learning logs for no-trade and AI-flow diagnosis."""

    def __init__(self, *, log_dir: Path) -> None:
        self._log_path = log_dir / "learning.jsonl"

    def build(self, *, tail_limit: int = 2000) -> dict[str, object]:
        events = self._read_tail(limit=tail_limit)
        event_counts = Counter(str(event.get("event_name")) for event in events)
        auto_cycles = [event for event in events if event.get("event_name") == "auto_trade_cycle"]
        fills = [event for event in events if event.get("event_name") == "fill_result"]
        signals = [event for event in events if event.get("event_name") == "signal_generated"]
        external_context_samples = self._external_context_samples(events)
        blocked_reasons = Counter(
            str((event.get("payload") or {}).get("reason"))
            for event in auto_cycles
            if (event.get("payload") or {}).get("reason") is not None
        )
        sizing_blocked_reasons = Counter(
            str((event.get("payload") or {}).get("sizing_blocked_reason"))
            for event in auto_cycles
            if (event.get("payload") or {}).get("sizing_blocked_reason") is not None
        )
        signal_reason_codes: Counter[str] = Counter()
        for event in signals:
            reason_codes = (event.get("payload") or {}).get("reason_codes") or []
            if isinstance(reason_codes, list):
                signal_reason_codes.update(str(code) for code in reason_codes)

        return {
            "status": "ok" if events else "empty",
            "log_path": str(self._log_path),
            "events_scanned": len(events),
            "event_counts": dict(event_counts),
            "last_event": None if not events else events[-1],
            "last_signal": None if not signals else signals[-1],
            "last_fill": None if not fills else fills[-1],
            "last_auto_cycle": None if not auto_cycles else auto_cycles[-1],
            "auto_cycle_status_counts": dict(
                Counter(str((event.get("payload") or {}).get("status")) for event in auto_cycles),
            ),
            "auto_cycle_blocked_reasons": dict(blocked_reasons),
            "sizing_blocked_reasons": dict(sizing_blocked_reasons),
            "signal_reason_codes": dict(signal_reason_codes),
            "external_context_summary": self._external_context_summary(external_context_samples),
            "market_state_summary": self._market_state_summary(events),
            "stop_loss_summary": self._stop_loss_summary(events),
            "no_trade_summary": self._no_trade_summary(events),
            "diagnosis": self._diagnose(
                events=events,
                auto_cycles=auto_cycles,
                fills=fills,
                blocked_reasons=blocked_reasons,
                sizing_blocked_reasons=sizing_blocked_reasons,
            ),
            "mitigation": self._mitigation(
                fills=fills,
                blocked_reasons=blocked_reasons,
                sizing_blocked_reasons=sizing_blocked_reasons,
            ),
        }

    def _read_tail(self, *, limit: int) -> list[dict[str, Any]]:
        return tail_jsonl_objects(self._log_path, limit=limit)

    @staticmethod
    def _external_context_samples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        for event in events:
            event_name = str(event.get("event_name", ""))
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            context = payload.get("external_context") if event_name == "auto_trade_cycle" else payload
            if event_name in {"auto_trade_cycle", "external_market_context_snapshot"} and isinstance(context, dict):
                samples.append(context)
        return samples

    @staticmethod
    def _external_context_summary(samples: list[dict[str, Any]]) -> dict[str, object]:
        if not samples:
            return {
                "sample_count": 0,
                "onchain_state_counts": {},
                "etf_state_counts": {},
                "avg_learning_weight": 1.0,
            }
        onchain_counts: Counter[str] = Counter()
        etf_counts: Counter[str] = Counter()
        etf_stale_count = 0
        weights: list[float] = []
        for sample in samples:
            onchain = sample.get("onchain") or {}
            etf = sample.get("etf") or {}
            etf_stale = False
            if isinstance(onchain, dict):
                onchain_counts.update([str(onchain.get("state") or "unknown")])
            if isinstance(etf, dict):
                etf_stale = ExternalMarketContextService._is_stale_flow_date(
                    str(etf.get("flow_date") or ""),
                    now=datetime.now(UTC),
                ) or bool(etf.get("stale"))
                etf_stale_count += 1 if etf_stale else 0
                etf_counts.update(["unknown" if etf_stale else str(etf.get("state") or "unknown")])
            try:
                weights.append(1.0 if etf_stale else float(sample.get("learning_weight", 1.0)))
            except (TypeError, ValueError):
                pass
        return {
            "sample_count": len(samples),
            "onchain_state_counts": dict(onchain_counts),
            "etf_state_counts": dict(etf_counts),
            "etf_stale_count": etf_stale_count,
            "avg_learning_weight": round(sum(weights) / len(weights), 3) if weights else 1.0,
        }

    @staticmethod
    def _market_state_summary(events: list[dict[str, Any]]) -> dict[str, object]:
        state_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        latest_state = None
        latest_label = None
        latest_box_range = {"low": None, "high": None}
        for event in events:
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            state = payload.get("market_state")
            if state not in {"bull", "bear", "box"}:
                continue
            state_counts.update([str(state)])
            source_counts.update([str(payload.get("market_state_source") or "payload")])
            latest_state = str(state)
            latest_label = payload.get("market_state_label")
            latest_box_range = {
                "low": payload.get("box_range_low"),
                "high": payload.get("box_range_high"),
            }
        return {
            "sample_count": sum(state_counts.values()),
            "state_counts": dict(state_counts),
            "source_counts": dict(source_counts),
            "latest_state": latest_state,
            "latest_state_label": latest_label,
            "latest_box_range": latest_box_range,
        }

    @staticmethod
    def _stop_loss_summary(events: list[dict[str, Any]]) -> dict[str, object]:
        exit_events = [event for event in events if event.get("event_name") == "position_exit_completed"]
        if not exit_events:
            exit_events = [
                event
                for event in events
                if event.get("event_name") == "position_lifecycle_updated"
                and ((event.get("payload") or {}).get("event_type") == "closed")
            ]
        reason_counts: Counter[str] = Counter()
        market_state_counts: Counter[str] = Counter()
        signal_level_counts: Counter[str] = Counter()
        take_profit_counts: Counter[str] = Counter()
        returns: list[float] = []
        take_profit_returns: list[float] = []
        elapsed_values: list[float] = []
        recent_stop_losses: list[dict[str, object]] = []
        for event in exit_events:
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            reason_code = str(payload.get("reason_code") or "")
            return_pct = LearningLogDiagnostics._exit_return_pct(payload)
            if reason_code.startswith("STOP_LOSS"):
                reason_counts.update([reason_code])
                state = payload.get("market_state")
                if state in {"bull", "bear", "box"}:
                    market_state_counts.update([str(state)])
                signal_level = payload.get("signal_level")
                if signal_level is not None:
                    signal_level_counts.update([str(signal_level)])
                if return_pct is not None:
                    returns.append(return_pct)
                try:
                    elapsed_values.append(float(payload.get("elapsed_sec")))
                except (TypeError, ValueError):
                    pass
                recent_stop_losses.append(
                    {
                        "recorded_at": event.get("recorded_at"),
                        "reason_code": reason_code,
                        "market_state": payload.get("market_state"),
                        "signal_level": signal_level,
                        "return_pct": return_pct,
                        "momentum_score": payload.get("momentum_score"),
                        "orderbook_imbalance": payload.get("orderbook_imbalance"),
                    },
                )
                continue
            if reason_code in {"TAKE_PROFIT_TARGET_HIT", "BOX_RANGE_HIGH_TAKE_PROFIT"}:
                take_profit_counts.update([reason_code])
                if return_pct is not None:
                    take_profit_returns.append(return_pct)
        total_stop_losses = sum(reason_counts.values())
        total_profit_exits = sum(take_profit_counts.values())
        return {
            "total_stop_losses": total_stop_losses,
            "reason_counts": dict(reason_counts),
            "market_state_counts": dict(market_state_counts),
            "signal_level_counts": dict(signal_level_counts),
            "avg_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
            "avg_elapsed_sec": round(sum(elapsed_values) / len(elapsed_values), 2) if elapsed_values else None,
            "profit_exit_counts": dict(take_profit_counts),
            "avg_profit_exit_return_pct": round(sum(take_profit_returns) / len(take_profit_returns), 6) if take_profit_returns else None,
            "stop_loss_to_profit_exit_ratio": (
                None if total_profit_exits <= 0 else round(total_stop_losses / total_profit_exits, 4)
            ),
            "recent_stop_losses": recent_stop_losses[-5:],
        }

    @staticmethod
    def _no_trade_summary(events: list[dict[str, Any]]) -> dict[str, object]:
        event_times = [LearningLogDiagnostics._parse_dt(event.get("recorded_at")) for event in events]
        event_times = [item for item in event_times if item is not None]
        if not event_times:
            return {"status": "unknown", "window_hours": 24}
        last_event_at = max(event_times)
        window_start = last_event_at - timedelta(hours=24)
        window_events = [
            event for event in events
            if (LearningLogDiagnostics._parse_dt(event.get("recorded_at")) or datetime.min.replace(tzinfo=UTC)) >= window_start
        ]
        cycles = [event for event in window_events if event.get("event_name") == "auto_trade_cycle"]
        fills = [event for event in window_events if event.get("event_name") == "fill_result"]
        reasons = Counter(
            str((event.get("payload") or {}).get("reason"))
            for event in cycles
            if (event.get("payload") or {}).get("reason") is not None
        )
        states = Counter(
            str((event.get("payload") or {}).get("market_state"))
            for event in cycles
            if (event.get("payload") or {}).get("market_state") in {"bull", "bear", "box"}
        )
        last_fill_times = [
            LearningLogDiagnostics._parse_dt(event.get("recorded_at"))
            for event in events
            if event.get("event_name") == "fill_result"
        ]
        last_fill_times = [item for item in last_fill_times if item is not None]
        last_fill_at = max(last_fill_times) if last_fill_times else None
        return {
            "window_hours": 24,
            "window_start_at": window_start.isoformat(),
            "last_event_at": last_event_at.isoformat(),
            "last_fill_at": None if last_fill_at is None else last_fill_at.isoformat(),
            "hours_since_last_fill": None if last_fill_at is None else round((last_event_at - last_fill_at).total_seconds() / 3600, 2),
            "window_cycle_count": len(cycles),
            "window_fill_count": len(fills),
            "blocked_reason_counts": dict(reasons),
            "market_state_counts": dict(states),
        }

    @staticmethod
    def _exit_return_pct(payload: dict[str, Any]) -> float | None:
        direct = payload.get("unrealized_return_pct")
        if direct is not None:
            try:
                return float(direct)
            except (TypeError, ValueError):
                pass
        try:
            entry = float(payload.get("entry_price", 0.0) or 0.0)
            current = float(payload.get("current_price", 0.0) or 0.0)
        except (TypeError, ValueError):
            return None
        if entry <= 0 or current <= 0:
            return None
        return round((current - entry) / entry, 6)

    @staticmethod
    def _parse_dt(value: object) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _diagnose(
        *,
        events: list[dict[str, Any]],
        auto_cycles: list[dict[str, Any]],
        fills: list[dict[str, Any]],
        blocked_reasons: Counter[str],
        sizing_blocked_reasons: Counter[str],
    ) -> dict[str, object]:
        if not events:
            return {
                "state": "NO_LEARNING_LOG",
                "message": "학습 로그가 없어 AI 판단 흐름을 진단할 수 없습니다.",
            }
        if not auto_cycles:
            return {
                "state": "AUTO_TRADING_NOT_RUNNING",
                "message": "최근 로그에 auto_trade_cycle이 없어 서버 자동매매 루프가 실행되지 않았거나 새 코드 적용 전 로그입니다.",
            }
        if fills:
            return {
                "state": "TRADES_FOUND",
                "message": "최근 로그에서 체결 이벤트가 확인됩니다. 무거래라면 조회 기간 또는 서버 재시작 시점을 확인하세요.",
            }
        if blocked_reasons or sizing_blocked_reasons:
            return {
                "state": "TRADE_BLOCKED_BY_RULES",
                "message": "자동매매 루프는 실행됐지만 리스크/신호/사이징 규칙이 진입을 차단했습니다.",
            }
        return {
            "state": "WAITING_FOR_SIGNAL",
            "message": "자동매매 루프가 실행 중이지만 아직 체결 조건이 충족되지 않았습니다.",
        }

    @staticmethod
    def _mitigation(
        *,
        fills: list[dict[str, Any]],
        blocked_reasons: Counter[str],
        sizing_blocked_reasons: Counter[str],
    ) -> dict[str, object]:
        if fills:
            return {
                "action": "NONE",
                "message": "최근 체결이 있어 완화 조치가 필요하지 않습니다.",
            }
        strict_blocks = (
            blocked_reasons.get("AUTO_MIN_SIGNAL_LEVEL", 0)
            + blocked_reasons.get("FEE_ADJUSTED_EDGE_LIMIT", 0)
            + sizing_blocked_reasons.get("FEE_ADJUSTED_EDGE_LIMIT", 0)
        )
        if strict_blocks >= 3:
            return {
                "action": "RELAX_ENTRY_RULES_FOR_DEMO",
                "message": "진입 규칙 차단만 반복됩니다. demo에서는 최소 신호 점수 완화, ETF/온체인 컨텍스트 가중치 확인, replay 후 룰 개선안을 생성하세요.",
                "blocked_count": strict_blocks,
            }
        return {
            "action": "MONITOR",
            "message": "차단 원인을 더 수집한 뒤 룰 개선 여부를 판단하세요.",
        }
