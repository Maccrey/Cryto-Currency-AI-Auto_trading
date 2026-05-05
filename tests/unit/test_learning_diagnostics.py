from __future__ import annotations

from pathlib import Path

from app.services.learning.diagnostics import LearningLogDiagnostics
from app.services.learning.service import LearningEvent, LearningService


def test_learning_log_diagnostics_reports_auto_trading_not_running(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)
    service.record(
        LearningEvent(
            event_name="signal_generated",
            market="KRW-XRP",
            mode="demo",
            payload={"blocked": False, "reason_codes": ["MOMENTUM_BREAKOUT"]},
        ),
    )

    diagnostics = LearningLogDiagnostics(log_dir=tmp_path).build()

    assert diagnostics["diagnosis"]["state"] == "AUTO_TRADING_NOT_RUNNING"
    assert diagnostics["last_signal"] is not None


def test_learning_log_diagnostics_reports_blocked_rules(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)
    service.record(
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={
                "status": "blocked",
                "reason": "SIGNAL_BLOCKED",
                "sizing_blocked_reason": "SIGNAL_BLOCKED",
            },
        ),
    )

    diagnostics = LearningLogDiagnostics(log_dir=tmp_path).build()

    assert diagnostics["diagnosis"]["state"] == "TRADE_BLOCKED_BY_RULES"
    assert diagnostics["auto_cycle_blocked_reasons"] == {"SIGNAL_BLOCKED": 1}
    assert diagnostics["sizing_blocked_reasons"] == {"SIGNAL_BLOCKED": 1}


def test_learning_log_diagnostics_recommends_demo_relaxation_after_repeated_rule_blocks(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)
    for reason in ["AUTO_MIN_SIGNAL_LEVEL", "AUTO_MIN_SIGNAL_LEVEL", "FEE_ADJUSTED_EDGE_LIMIT"]:
        service.record(
            LearningEvent(
                event_name="auto_trade_cycle",
                market="KRW-BTC",
                mode="demo",
                payload={
                    "status": "blocked",
                    "reason": reason,
                    "sizing_blocked_reason": reason,
                },
            ),
        )

    diagnostics = LearningLogDiagnostics(log_dir=tmp_path).build()

    assert diagnostics["diagnosis"]["state"] == "TRADE_BLOCKED_BY_RULES"
    assert diagnostics["mitigation"]["action"] == "RELAX_ENTRY_RULES_FOR_DEMO"


def test_learning_log_diagnostics_reports_found_trades(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)
    service.record(
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-XRP",
            mode="demo",
            payload={"status": "filled", "reason": None},
        ),
    )
    service.record(
        LearningEvent(
            event_name="fill_result",
            market="KRW-XRP",
            mode="demo",
            payload={"side": "buy"},
        ),
    )

    diagnostics = LearningLogDiagnostics(log_dir=tmp_path).build()

    assert diagnostics["diagnosis"]["state"] == "TRADES_FOUND"
    assert diagnostics["last_fill"] is not None


def test_learning_log_diagnostics_summarizes_external_market_context(tmp_path: Path) -> None:
    service = LearningService(log_dir=tmp_path)
    service.record(
        LearningEvent(
            event_name="auto_trade_cycle",
            market="KRW-BTC",
            mode="demo",
            payload={
                "status": "blocked",
                "reason": "AUTO_MIN_SIGNAL_LEVEL",
                "external_context": {
                    "onchain": {"state": "bullish"},
                    "etf": {"state": "inflow"},
                    "learning_weight": 1.2,
                },
            },
        ),
    )
    service.record(
        LearningEvent(
            event_name="external_market_context_snapshot",
            market="KRW-BTC",
            mode="demo",
            payload={
                "onchain": {"state": "bearish"},
                "etf": {"state": "outflow"},
                "learning_weight": 0.8,
            },
        ),
    )

    diagnostics = LearningLogDiagnostics(log_dir=tmp_path).build()

    assert diagnostics["external_context_summary"]["sample_count"] == 2
    assert diagnostics["external_context_summary"]["onchain_state_counts"] == {"bullish": 1, "bearish": 1}
    assert diagnostics["external_context_summary"]["etf_state_counts"] == {"inflow": 1, "outflow": 1}
    assert diagnostics["external_context_summary"]["avg_learning_weight"] == 1.0
