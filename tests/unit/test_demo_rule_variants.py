from __future__ import annotations

from app.services.learning.service import LearningEvent
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.signals.features import FeatureSnapshot
from app.services.sizing.engine import SizingDecision
from app.services.trading.decision import TradeDecisionResult
from app.services.trading.variants import DemoRuleVariantSelector


def _decision(*, market_state: str, signal_level: str = "strong") -> TradeDecisionResult:
    return TradeDecisionResult(
        features=FeatureSnapshot(
            ret_1s=0.01,
            ret_5s=0.012,
            ret_30s=0.02,
            volume_multiple=1.2,
            traded_value_multiple=1.2,
            spread_bps=8.0,
            orderbook_imbalance=0.1,
            short_volatility=0.01,
            regime_score=0.7,
            liquidity_score=0.8,
        ),
        signal=SignalDecision(
            score=0.72,
            level=signal_level,
            blocked=False,
            reason_codes=[],
        ),
        regime=RegimeSnapshot(
            label="risk_on",
            score=0.7,
            size_multiplier=1.0,
            entry_allowed=True,
            reason_codes=[],
            market_state=market_state,
            market_state_label={"bull": "상승장", "bear": "하락장", "box": "박스권"}[market_state],
            box_range_low=None,
            box_range_high=None,
        ),
        sizing=SizingDecision(
            allowed=True,
            order_side="buy",
            buy_ratio=0.2,
            buy_amount=100_000,
            buy_quantity=100,
        ),
    )


def test_demo_rule_variant_selector_prefers_trend_rule_in_bull_market() -> None:
    selector = DemoRuleVariantSelector()

    selection = selector.select(decision=_decision(market_state="bull"), recent_events=[])

    assert selection.selected.key == "B"
    assert selection.selected.buy_multiplier > 1.0


def test_demo_rule_variant_selector_uses_recent_demo_learning_result() -> None:
    selector = DemoRuleVariantSelector()
    recent_events = [
        LearningEvent(
            event_name="rule_variant_result",
            market="KRW-XRP",
            mode="demo",
            payload={
                "status": "filled",
                "rule_variant_key": "C",
                "realized_pnl": 1200,
                "rule_variant_expected_return_hint": 0.012,
            },
        )
        for _ in range(8)
    ]

    selection = selector.select(
        decision=_decision(market_state="box", signal_level="weak"),
        recent_events=recent_events,
    )

    assert selection.selected.key == "C"
    assert "최근 데모 학습 결과 반영" in selection.reason
