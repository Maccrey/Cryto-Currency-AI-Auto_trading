from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.signals.features import FeatureSnapshot
from app.services.sizing.engine import SizingDecision
from app.services.trading.decision import TradeDecisionResult
from app.services.trading.variants import DemoRuleVariantShadowTester


def _decision(*, market_state: str, signal_level: str = "strong", buy_amount: float = 100_000) -> TradeDecisionResult:
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
            buy_amount=buy_amount,
            buy_quantity=100,
            sell_ratio=0.3,
        ),
    )


def test_demo_rule_variant_shadow_tester_runs_all_rules_on_same_tick() -> None:
    tester = DemoRuleVariantShadowTester()

    report = tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=PortfolioState(
            cash_balance=1_000_000,
            asset_currency="XRP",
            asset_balance=0,
            avg_buy_price=0,
        ),
    )

    assert {item["variant_key"] for item in report["results"]} == {"A", "B", "C"}
    assert report["leader_key"] in {"A", "B", "C"}
    assert all(item["last_action"] == "buy" for item in report["results"])


def test_demo_rule_variant_shadow_tester_compares_profit_rate_after_same_price_move() -> None:
    tester = DemoRuleVariantShadowTester()
    portfolio = PortfolioState(
        cash_balance=1_000_000,
        asset_currency="XRP",
        asset_balance=0,
        avg_buy_price=0,
    )
    tester.evaluate(decision=_decision(market_state="bull"), current_price=1_000, portfolio=portfolio)

    report = tester.evaluate(decision=_decision(market_state="bull"), current_price=1_012, portfolio=portfolio)

    results = {item["variant_key"]: item for item in report["results"]}
    assert results["B"]["profit_rate"] > results["A"]["profit_rate"]
    assert results["A"]["profit_rate"] > results["C"]["profit_rate"]
    assert report["leader_key"] == "B"
