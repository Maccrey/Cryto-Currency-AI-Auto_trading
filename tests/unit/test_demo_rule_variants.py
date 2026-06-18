from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.signals.features import FeatureSnapshot
from app.services.sizing.engine import SizingDecision
from app.services.trading.decision import TradeDecisionResult
from app.services.trading.variants import DemoRuleVariantShadowTester


def _decision(
    *,
    market_state: str,
    signal_level: str = "strong",
    buy_amount: float = 100_000,
    box_range_low: float | None = None,
    box_range_high: float | None = None,
) -> TradeDecisionResult:
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
            box_range_low=box_range_low,
            box_range_high=box_range_high,
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

    assert {item["variant_key"] for item in report["results"]} == {"A", "B", "C", "D", "E", "F"}
    assert report["leader_key"] is None
    assert report["promotion_eligible"] is False
    assert report["candidate_leader_key"] in {"A", "B", "C", "D", "E", "F"}
    assert {item["variant_key"] for item in report["results"] if item["last_action"] == "buy"} == {
        "A",
        "B",
        "C",
        "D",
        "F",
    }
    assert all("effective_buy_multiplier" in item for item in report["results"])
    assert report["market_state"] == "bull"


def test_demo_rule_variant_trend_rule_buys_only_in_bull_market() -> None:
    for market_state in ("bear", "box"):
        tester = DemoRuleVariantShadowTester()

        report = tester.evaluate(
            decision=_decision(market_state=market_state),
            current_price=1_000,
            portfolio=PortfolioState(
                cash_balance=1_000_000,
                asset_currency="XRP",
                asset_balance=0,
                avg_buy_price=0,
            ),
        )

        results = {item["variant_key"]: item for item in report["results"]}
        assert results["B"]["last_action"] == "hold"
        assert results["B"]["asset_balance"] == 0
        assert results["B"]["cash_balance"] == 1_000_000


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
    assert report["leader_key"] is None
    assert report["candidate_leader_key"] in {"B", "D"}


def test_demo_rule_variant_defensive_rule_buys_only_near_box_low() -> None:
    tester = DemoRuleVariantShadowTester()
    portfolio = PortfolioState(
        cash_balance=1_000_000,
        asset_currency="XRP",
        asset_balance=0,
        avg_buy_price=0,
    )

    low_report = tester.evaluate(
        decision=_decision(market_state="box", box_range_low=980.0, box_range_high=1_040.0),
        current_price=990.0,
        portfolio=portfolio,
    )

    results = {item["variant_key"]: item for item in low_report["results"]}
    assert results["C"]["last_action"] == "buy"
    assert results["C"]["action_reason"] == "box_low_defensive_entry"
    assert results["C"]["box_position"] < 0.35

    high_tester = DemoRuleVariantShadowTester()
    high_report = high_tester.evaluate(
        decision=_decision(market_state="box", box_range_low=980.0, box_range_high=1_040.0),
        current_price=1_030.0,
        portfolio=portfolio,
    )

    high_results = {item["variant_key"]: item for item in high_report["results"]}
    assert high_results["C"]["last_action"] == "hold"
    assert high_results["C"]["entry_allowed_by_variant"] is False
    assert high_results["C"]["action_reason"] == "box_mid_high_entry_block"


def test_demo_rule_variant_bear_market_sells_defensive_rule_more_aggressively() -> None:
    tester = DemoRuleVariantShadowTester()
    portfolio = PortfolioState(
        cash_balance=900_000,
        asset_currency="XRP",
        asset_balance=100,
        avg_buy_price=1_000,
    )

    report = tester.evaluate(
        decision=_decision(market_state="bear", buy_amount=0),
        current_price=990.0,
        portfolio=portfolio,
    )

    results = {item["variant_key"]: item for item in report["results"]}
    assert results["A"]["last_action"] == "sell"
    assert results["C"]["last_action"] == "sell"
    assert results["C"]["effective_sell_multiplier"] > results["A"]["effective_sell_multiplier"]
    assert results["C"]["asset_balance"] < results["A"]["asset_balance"]
    assert results["C"]["action_reason"] == "bear_defensive_exit"


def test_demo_rule_variant_shadow_tester_tracks_stop_loss_and_drawdown() -> None:
    tester = DemoRuleVariantShadowTester()
    portfolio = PortfolioState(
        cash_balance=1_000_000,
        asset_currency="XRP",
        asset_balance=0,
        avg_buy_price=0,
    )
    tester.evaluate(decision=_decision(market_state="bull"), current_price=1_000, portfolio=portfolio)

    report = tester.evaluate(decision=_decision(market_state="bull"), current_price=990, portfolio=portfolio)

    results = {item["variant_key"]: item for item in report["results"]}
    assert results["A"]["stop_loss_count"] == 1
    assert results["A"]["loss_count"] == 1
    assert results["A"]["max_drawdown_pct"] > 0


def test_demo_rule_variant_shadow_tester_explores_weak_bull_candidates() -> None:
    tester = DemoRuleVariantShadowTester()

    report = tester.evaluate(
        decision=_decision(market_state="bull", signal_level="weak"),
        current_price=1_000,
        portfolio=PortfolioState(
            cash_balance=1_000_000,
            asset_currency="XRP",
            asset_balance=0,
            avg_buy_price=0,
        ),
    )

    results = {item["variant_key"]: item for item in report["results"]}
    assert results["A"]["last_action"] == "buy"
    assert results["B"]["last_action"] == "buy"
    assert results["C"]["last_action"] == "buy"
    assert results["B"]["effective_buy_multiplier"] > results["A"]["effective_buy_multiplier"]
    assert results["C"]["effective_stop_loss_pct"] < results["A"]["effective_stop_loss_pct"]
    assert results["D"]["last_action"] == "hold"
    assert results["E"]["last_action"] == "hold"
    assert results["F"]["last_action"] == "hold"


def test_demo_rule_variant_shadow_tester_resets_all_candidate_results() -> None:
    tester = DemoRuleVariantShadowTester()
    portfolio = PortfolioState(
        cash_balance=1_000_000,
        asset_currency="XRP",
        asset_balance=0,
        avg_buy_price=0,
    )
    tester.evaluate(decision=_decision(market_state="bull"), current_price=1_000, portfolio=portfolio)
    tester.reset()

    report = tester.evaluate(decision=_decision(market_state="bull"), current_price=1_000, portfolio=portfolio)

    assert all(item["trade_count"] == 0 for item in report["results"])
    assert all(item["profit_rate"] <= 0 for item in report["results"])
    assert report["leader_key"] is None
