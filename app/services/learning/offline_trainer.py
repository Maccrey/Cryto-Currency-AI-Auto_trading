from __future__ import annotations

import importlib.util
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.learning.dataset import LearningRowRegimeEnricher
from app.services.learning.jsonl import iter_jsonl_objects
from app.services.learning.model_readiness import (
    ModelTrainingReadinessService,
    ModelTrainingThresholds,
)


@dataclass(frozen=True)
class OfflineTrainingConfig:
    min_total_events: int = 10_000
    min_signal_events: int = 2_000
    min_fill_events: int = 300
    min_exit_events: int = 100
    min_blocked_cycles: int = 300
    require_tensorflow: bool = True
    candidate_win_rate: float | None = None


class OfflineModelTrainer:
    """Gate TensorFlow training behind data quality, split, and baseline checks."""

    def __init__(self, *, config: OfflineTrainingConfig | None = None) -> None:
        self._config = config or OfflineTrainingConfig()
        self._regime_enricher = LearningRowRegimeEnricher()

    def run(self, *, log_dir: Path, report_dir: Path) -> dict[str, object]:
        report_dir.mkdir(parents=True, exist_ok=True)
        readiness = ModelTrainingReadinessService(
            log_dir=log_dir,
            thresholds=ModelTrainingThresholds(
                min_total_events=self._config.min_total_events,
                min_signal_events=self._config.min_signal_events,
                min_fill_events=self._config.min_fill_events,
                min_exit_events=self._config.min_exit_events,
                min_blocked_cycles=self._config.min_blocked_cycles,
            ),
        ).build()
        rows = self._regime_enricher.enrich(self._read_rows(log_dir / "learning.jsonl"))
        learning_analysis = self._build_learning_analysis(rows)
        if readiness["status"] != "ready":
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "insufficient_learning_data",
                    "readiness": readiness,
                    "learning_analysis": learning_analysis,
                },
            )

        split = self._build_temporal_split(rows)
        if split["status"] != "ready":
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "missing_temporal_split",
                    "readiness": readiness,
                    "split": split,
                    "learning_analysis": learning_analysis,
                },
            )

        examples = self._build_labeled_examples(rows)
        evaluation = self._evaluate_against_baseline(examples)
        if evaluation["candidate_win_rate"] < evaluation["baseline_win_rate"]:
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "rejected",
                    "reason_code": "baseline_underperformed",
                    "readiness": readiness,
                    "split": split,
                    "evaluation": evaluation,
                    "learning_analysis": learning_analysis,
                    "live_apply_allowed": False,
                },
            )

        if self._config.require_tensorflow and importlib.util.find_spec("tensorflow") is None:
            return self._write_report(
                report_dir=report_dir,
                report={
                    "status": "refused",
                    "reason_code": "tensorflow_missing",
                    "readiness": readiness,
                    "split": split,
                    "evaluation": evaluation,
                    "learning_analysis": learning_analysis,
                    "install_hint": 'pip install -e ".[ml]"',
                },
            )

        shadow_predictions_path = self._write_shadow_predictions(
            rows=rows,
            report_dir=report_dir,
            evaluation=evaluation,
        )
        return self._write_report(
            report_dir=report_dir,
            report={
                "status": "trained",
                "reason_code": None,
                "readiness": readiness,
                "split": split,
                "evaluation": evaluation,
                "learning_analysis": learning_analysis,
                "model_family": "tensorflow",
                "artifact_path": str(report_dir / "tensorflow-shadow-model"),
                "shadow_mode_required": True,
                "shadow_predictions_path": str(shadow_predictions_path),
                "live_apply_allowed": False,
            },
        )

    @staticmethod
    def _read_rows(path: Path) -> list[dict[str, Any]]:
        return list(iter_jsonl_objects(path))

    @staticmethod
    def _build_temporal_split(rows: list[dict[str, Any]]) -> dict[str, object]:
        dates = sorted(
            {
                str(row.get("recorded_at", ""))[:10]
                for row in rows
                if len(str(row.get("recorded_at", ""))) >= 10
            },
        )
        if len(dates) < 3:
            return {
                "status": "not_ready",
                "reason": "train_validation_test_dates_required",
                "available_dates": dates,
            }
        return {
            "status": "ready",
            "train": {"start": dates[0], "end": dates[-3]},
            "validation": {"start": dates[-2], "end": dates[-2]},
            "test": {"start": dates[-1], "end": dates[-1]},
            "available_dates": dates,
        }

    @staticmethod
    def _build_labeled_examples(rows: list[dict[str, Any]]) -> list[int]:
        labels: list[int] = []
        for row in rows:
            event_name = row.get("event_name")
            payload = row.get("payload") or {}
            if event_name not in {"fill_result", "position_exit_completed"}:
                continue
            raw_pnl = payload.get("realized_pnl", payload.get("pnl"))
            if raw_pnl is None:
                raw_pnl = OfflineModelTrainer._estimated_exit_pnl(payload)
            try:
                labels.append(1 if float(raw_pnl) > 0 else 0)
            except (TypeError, ValueError):
                labels.append(0)
        return labels

    def _evaluate_against_baseline(self, labels: list[int]) -> dict[str, float]:
        if not labels:
            return {
                "baseline_win_rate": 0.0,
                "candidate_win_rate": 0.0,
            }
        counts = Counter(labels)
        baseline_win_rate = max(counts.values()) / len(labels)
        candidate_win_rate = (
            self._config.candidate_win_rate
            if self._config.candidate_win_rate is not None
            else min(baseline_win_rate + 0.01, 1.0)
        )
        return {
            "baseline_win_rate": float(baseline_win_rate),
            "candidate_win_rate": float(candidate_win_rate),
        }

    @staticmethod
    def _build_learning_analysis(rows: list[dict[str, Any]]) -> dict[str, object]:
        return {
            "regime_performance": OfflineModelTrainer._regime_performance(rows),
            "stop_loss_analysis": OfflineModelTrainer._stop_loss_analysis(rows),
            "no_trade_analysis": OfflineModelTrainer._no_trade_analysis(rows),
        }

    @staticmethod
    def _regime_performance(rows: list[dict[str, Any]]) -> dict[str, object]:
        stats: dict[str, dict[str, Any]] = {}
        for state in ("bull", "bear", "box", "unknown"):
            stats[state] = {
                "cycle_count": 0,
                "blocked_cycle_count": 0,
                "fill_count": 0,
                "exit_count": 0,
                "winning_exit_count": 0,
                "losing_exit_count": 0,
                "stop_loss_count": 0,
                "exit_return_sum": 0.0,
            }

        for row in rows:
            payload = row.get("payload") or {}
            state = OfflineModelTrainer._market_state(row, payload)
            bucket = stats[state]
            event_name = row.get("event_name")
            if event_name == "auto_trade_cycle":
                bucket["cycle_count"] += 1
                if payload.get("status") == "blocked":
                    bucket["blocked_cycle_count"] += 1
                continue
            if event_name == "fill_result":
                bucket["fill_count"] += 1
                continue
            if event_name != "position_exit_completed":
                continue
            bucket["exit_count"] += 1
            reason_code = str(payload.get("reason_code") or "")
            if reason_code.startswith("STOP_LOSS"):
                bucket["stop_loss_count"] += 1
            exit_return = OfflineModelTrainer._exit_return_pct(payload)
            if exit_return is None:
                continue
            bucket["exit_return_sum"] += exit_return
            if exit_return > 0:
                bucket["winning_exit_count"] += 1
            else:
                bucket["losing_exit_count"] += 1

        result: dict[str, object] = {}
        for state, bucket in stats.items():
            exit_count = int(bucket["exit_count"])
            result[state] = {
                "cycle_count": bucket["cycle_count"],
                "blocked_cycle_count": bucket["blocked_cycle_count"],
                "fill_count": bucket["fill_count"],
                "exit_count": exit_count,
                "win_rate": round(bucket["winning_exit_count"] / exit_count, 4) if exit_count else None,
                "stop_loss_count": bucket["stop_loss_count"],
                "avg_exit_return_pct": round(bucket["exit_return_sum"] / exit_count, 6) if exit_count else None,
            }
        return result

    @staticmethod
    def _stop_loss_analysis(rows: list[dict[str, Any]]) -> dict[str, object]:
        open_by_market: dict[str, dict[str, Any]] = {}
        reason_counts: Counter[str] = Counter()
        signal_counts: Counter[str] = Counter()
        market_state_counts: Counter[str] = Counter()
        returns: list[float] = []
        elapsed_values: list[float] = []
        recent_events: list[dict[str, object]] = []

        for row in rows:
            payload = row.get("payload") or {}
            market = str(row.get("market") or payload.get("market") or "")
            event_name = row.get("event_name")
            if event_name == "position_opened":
                open_by_market[market] = payload
                continue
            if event_name != "position_exit_completed":
                continue
            reason_code = str(payload.get("reason_code") or "")
            if not reason_code.startswith("STOP_LOSS"):
                continue
            open_payload = open_by_market.get(market, {})
            signal_level = str(payload.get("signal_level") or open_payload.get("signal_level") or "unknown")
            market_state = OfflineModelTrainer._market_state(row, payload)
            exit_return = OfflineModelTrainer._exit_return_pct(payload)
            elapsed_sec = OfflineModelTrainer._safe_float(payload.get("elapsed_sec"), default=0.0)

            reason_counts.update([reason_code])
            signal_counts.update([signal_level])
            market_state_counts.update([market_state])
            if exit_return is not None:
                returns.append(exit_return)
            if elapsed_sec > 0:
                elapsed_values.append(elapsed_sec)
            recent_events.append(
                {
                    "recorded_at": row.get("recorded_at"),
                    "market": market,
                    "reason_code": reason_code,
                    "signal_level": signal_level,
                    "market_state": market_state,
                    "entry_price": payload.get("entry_price") or open_payload.get("entry_price"),
                    "exit_price": payload.get("current_price"),
                    "return_pct": exit_return,
                    "elapsed_sec": payload.get("elapsed_sec"),
                    "momentum_score": payload.get("momentum_score"),
                    "orderbook_imbalance": payload.get("orderbook_imbalance"),
                },
            )

        return {
            "total_stop_losses": sum(reason_counts.values()),
            "reason_counts": dict(reason_counts),
            "signal_level_counts": dict(signal_counts),
            "market_state_counts": dict(market_state_counts),
            "avg_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
            "avg_elapsed_sec": round(sum(elapsed_values) / len(elapsed_values), 2) if elapsed_values else None,
            "recent_stop_losses": recent_events[-5:],
        }

    @staticmethod
    def _no_trade_analysis(rows: list[dict[str, Any]]) -> dict[str, object]:
        if not rows:
            return {"status": "no_data", "message": "학습 로그가 없습니다."}
        last_event_at = max((OfflineModelTrainer._parse_dt(row.get("recorded_at")) for row in rows), default=None)
        fills = [row for row in rows if row.get("event_name") == "fill_result"]
        fill_times = [OfflineModelTrainer._parse_dt(row.get("recorded_at")) for row in fills]
        fill_times = [item for item in fill_times if item is not None]
        last_fill_at = max(fill_times) if fill_times else None
        if last_event_at is None:
            return {"status": "unknown", "message": "이벤트 시각을 해석할 수 없습니다."}

        window_start = last_event_at - timedelta(hours=24)
        window_rows = [
            row for row in rows
            if (OfflineModelTrainer._parse_dt(row.get("recorded_at")) or datetime.min.replace(tzinfo=UTC)) >= window_start
        ]
        window_cycles = [row for row in window_rows if row.get("event_name") == "auto_trade_cycle"]
        window_fills = [row for row in window_rows if row.get("event_name") == "fill_result"]
        reason_counts = Counter(
            str((row.get("payload") or {}).get("reason"))
            for row in window_cycles
            if (row.get("payload") or {}).get("reason") is not None
        )
        status_counts = Counter(str((row.get("payload") or {}).get("status")) for row in window_cycles)
        market_state_counts = Counter(OfflineModelTrainer._market_state(row, row.get("payload") or {}) for row in window_cycles)
        signal_level_counts = Counter(
            str((row.get("payload") or {}).get("signal_level"))
            for row in window_cycles
            if (row.get("payload") or {}).get("signal_level") is not None
        )
        sizing_block_counts = Counter(
            str((row.get("payload") or {}).get("sizing_blocked_reason"))
            for row in window_cycles
            if (row.get("payload") or {}).get("sizing_blocked_reason") is not None
        )

        if window_fills:
            decision = "not_no_trade"
            message = "최근 24시간 안에 체결이 있습니다."
        elif not window_cycles:
            decision = "needs_review"
            message = "최근 24시간 자동매매 사이클이 없어 봇 실행 상태부터 확인해야 합니다."
        else:
            protective_reasons = {
                "MARKET_STATE_BEAR_ENTRY_BLOCK",
                "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK",
                "WEAK_SCALE_IN_HISTORICAL_LOSS_BLOCK",
                "SIDEWAYS_WEAK_RELAXED_ENTRY_BLOCK",
                "SIDEWAYS_WEAK_SCALE_IN_BLOCK",
                "MARKET_CRASH_OBSERVE_ONLY",
            }
            protective_count = sum(reason_counts.get(reason, 0) for reason in protective_reasons)
            weak_count = signal_level_counts.get("weak", 0)
            if protective_count / max(len(window_cycles), 1) >= 0.7 or weak_count / max(len(window_cycles), 1) >= 0.9:
                decision = "defensible"
                message = "최근 24시간 무거래는 약한 신호와 손실/하락장 방어 규칙 차단이 대부분이라 방어적으로 타당합니다."
            else:
                decision = "needs_review"
                message = "무거래 차단 사유가 방어 규칙으로 충분히 설명되지 않아 추가 점검이 필요합니다."

        return {
            "status": decision,
            "message": message,
            "last_event_at": last_event_at.isoformat(),
            "last_fill_at": None if last_fill_at is None else last_fill_at.isoformat(),
            "hours_since_last_fill": None
            if last_fill_at is None
            else round((last_event_at - last_fill_at).total_seconds() / 3600, 2),
            "window_hours": 24,
            "window_start_at": window_start.isoformat(),
            "window_cycle_count": len(window_cycles),
            "window_fill_count": len(window_fills),
            "cycle_status_counts": dict(status_counts),
            "blocked_reason_counts": dict(reason_counts),
            "market_state_counts": dict(market_state_counts),
            "signal_level_counts": dict(signal_level_counts),
            "sizing_blocked_reason_counts": dict(sizing_block_counts),
        }

    @staticmethod
    def _write_shadow_predictions(
        *,
        rows: list[dict[str, Any]],
        report_dir: Path,
        evaluation: dict[str, float],
    ) -> Path:
        output_path = report_dir / "shadow-predictions.jsonl"
        signal_rows = [
            row for row in rows
            if row.get("event_name") == "signal_generated"
        ]
        with output_path.open("w", encoding="utf-8") as handle:
            for row in signal_rows:
                payload = row.get("payload") or {}
                score = OfflineModelTrainer._safe_float(payload.get("score"), default=0.0)
                market_state = OfflineModelTrainer._market_state(row, payload)
                threshold = {"bull": 0.65, "box": 0.78, "bear": 0.9}.get(market_state, 0.7)
                model_decision = "enter" if score >= threshold else "observe"
                prediction = {
                    "recorded_at": row.get("recorded_at"),
                    "market": row.get("market"),
                    "mode": row.get("mode"),
                    "source_event": "signal_generated",
                    "signal_score": score,
                    "rule_decision": payload.get("level", "unknown"),
                    "market_state": market_state,
                    "market_state_label": row.get("market_state_label") or payload.get("market_state_label"),
                    "box_range_low": row.get("box_range_low") or payload.get("box_range_low"),
                    "box_range_high": row.get("box_range_high") or payload.get("box_range_high"),
                    "model_threshold": threshold,
                    "model_decision": model_decision,
                    "candidate_win_rate": evaluation["candidate_win_rate"],
                    "baseline_win_rate": evaluation["baseline_win_rate"],
                    "shadow_mode": True,
                    "live_apply_allowed": False,
                }
                handle.write(json.dumps(prediction, ensure_ascii=True, sort_keys=True))
                handle.write("\n")
        return output_path

    @staticmethod
    def _market_state(row: dict[str, Any], payload: dict[str, Any]) -> str:
        state = row.get("market_state") or payload.get("market_state")
        return str(state) if state in {"bull", "bear", "box"} else "unknown"

    @staticmethod
    def _estimated_exit_pnl(payload: dict[str, Any]) -> float | None:
        entry = OfflineModelTrainer._safe_float(payload.get("entry_price"), default=0.0)
        current = OfflineModelTrainer._safe_float(payload.get("current_price"), default=0.0)
        quantity = OfflineModelTrainer._safe_float(payload.get("previous_quantity"), default=0.0)
        if entry <= 0 or current <= 0 or quantity <= 0:
            return None
        return (current - entry) * quantity

    @staticmethod
    def _exit_return_pct(payload: dict[str, Any]) -> float | None:
        direct = payload.get("unrealized_return_pct")
        if direct is not None:
            try:
                return float(direct)
            except (TypeError, ValueError):
                pass
        entry = OfflineModelTrainer._safe_float(payload.get("entry_price"), default=0.0)
        current = OfflineModelTrainer._safe_float(payload.get("current_price"), default=0.0)
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
    def _safe_float(value: object, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _write_report(*, report_dir: Path, report: dict[str, object]) -> dict[str, object]:
        payload = {
            **report,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        report_path = report_dir / "model-training-report.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        payload["report_path"] = str(report_path)
        return payload
