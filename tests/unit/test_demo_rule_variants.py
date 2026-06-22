from __future__ import annotations

from app.services.portfolio.sync import PortfolioState
from app.services.regime.engine import RegimeSnapshot
from app.services.signals.engine import SignalDecision
from app.services.signals.features import FeatureSnapshot
from app.services.sizing.engine import SizingDecision
from app.services.trading.decision import TradeDecisionResult
from app.services.trading.variants import DemoRuleVariantShadowTester, ShadowPortfolio


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

    assert {item["variant_key"] for item in report["results"]} == set("ABCDEFGHIJKLMNO")
    assert report["leader_key"] is None
    assert report["promotion_eligible"] is False
    assert report["candidate_leader_key"] in set("ABCDEFGHIJKLMNO")
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
    assert report["candidate_leader_key"] in {"B", "D", "O"}


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
    assert results["M"]["last_action"] == "hold"
    assert results["N"]["last_action"] == "hold"
    assert results["O"]["last_action"] == "hold"


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


def test_demo_rule_variant_candidate_uses_highest_profit_rate_even_when_all_negative() -> None:
    candidate = max(
        [
            {"variant_key": "A", "profit_rate": -0.0077, "max_drawdown_pct": 0.008, "trade_count": 100},
            {"variant_key": "B", "profit_rate": -0.0013, "max_drawdown_pct": 0.003, "trade_count": 80},
            {"variant_key": "C", "profit_rate": -0.0068, "max_drawdown_pct": 0.007, "trade_count": 20},
        ],
        key=DemoRuleVariantShadowTester._candidate_score,
    )

    assert candidate["variant_key"] == "B"


def test_demo_rule_variant_requires_twenty_closed_trades_for_normal_promotion() -> None:
    candidate = {
        "profit_rate": 0.02,
        "realized_pnl": 20_000.0,
        "trade_count": 19,
        "profit_factor": 2.0,
        "stop_loss_rate": 0.1,
    }

    assert DemoRuleVariantShadowTester._promotion_eligible(candidate) is False

    candidate["trade_count"] = 20
    assert DemoRuleVariantShadowTester._promotion_eligible(candidate) is True


def test_demo_rule_variant_positive_leader_switches_applied_entry_policy() -> None:
    tester = DemoRuleVariantShadowTester()
    tester._initial_equity = 1_000_000.0
    for variant in tester.DEFAULT_VARIANTS:
        tester._portfolios[variant.key] = ShadowPortfolio(
            cash_balance=1_000_000.0,
            asset_balance=0.0,
            avg_buy_price=0.0,
            trade_count=20,
            win_count=12,
            gross_profit=20_000.0,
            gross_loss=10_000.0,
            peak_equity=1_000_000.0,
        )
    tester._portfolios["B"].cash_balance = 1_020_000.0
    tester._portfolios["B"].realized_pnl = 20_000.0
    decision = _decision(market_state="bull", buy_amount=100_000)

    report = tester.evaluate(
        decision=decision,
        current_price=1_000.0,
        portfolio=PortfolioState(
            cash_balance=1_000_000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
    )
    applied = tester.apply_selected_variant(decision=decision, current_price=1_000.0)

    assert report["leader_key"] == "B"
    assert report["selection_changed"] is True
    assert report["applied_variant_key"] == "B"
    assert applied.sizing.buy_amount > decision.sizing.buy_amount


def test_demo_rule_variant_stop_loss_forced_switch() -> None:
    # ── 시나리오 1: 다른 룰들 중 양수(플러스) 수익률이 없는 경우 (스위칭 비활성) ──
    tester = DemoRuleVariantShadowTester()
    tester._applied_variant_key = "A"
    tester._initial_equity = 1_000_000.0

    tester._portfolios["A"] = ShadowPortfolio(
        cash_balance=0.0,
        asset_balance=1000.0,
        avg_buy_price=1000.0,
        peak_equity=1_000_000.0,
        trade_count=1,
    )
    # B는 수익률이 0% 상태
    tester._portfolios["B"] = ShadowPortfolio(
        cash_balance=1_000_000.0,
        asset_balance=0.0,
        avg_buy_price=0.0,
        peak_equity=1_000_000.0,
        trade_count=0,
    )

    decision = _decision(market_state="bear", buy_amount=0)
    report = tester.evaluate(
        decision=decision,
        current_price=900.0,
        portfolio=PortfolioState(
            cash_balance=1_000_000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
    )

    # 양수 수익률 룰이 없으므로 스위칭되지 않고 A 유지
    assert report["selection_changed"] is False
    assert report["applied_variant_key"] == "A"

    # ── 시나리오 2: 다른 룰들 중 양수(플러스) 수익률이 존재하는 경우 (스위칭 활성) ──
    tester2 = DemoRuleVariantShadowTester()
    tester2._applied_variant_key = "A"
    tester2._initial_equity = 1_000_000.0

    tester2._portfolios["A"] = ShadowPortfolio(
        cash_balance=0.0,
        asset_balance=1000.0,
        avg_buy_price=1000.0,
        peak_equity=1_000_000.0,
        trade_count=1,
    )
    # B는 수익률이 1% (1,010,000 KRW) 상태이며 실현 손익과 거래 횟수가 완결된 상태
    tester2._portfolios["B"] = ShadowPortfolio(
        cash_balance=1_010_000.0,
        asset_balance=0.0,
        avg_buy_price=0.0,
        peak_equity=1_010_000.0,
        trade_count=1,
        win_count=1,
        realized_pnl=10000.0,
    )

    report2 = tester2.evaluate(
        decision=decision,
        current_price=900.0,
        portfolio=PortfolioState(
            cash_balance=1_000_000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
    )

    # B가 양수(1%)이면서 실현 손익이 검증되었으므로 A에서 B로 강제 스위칭되어야 함
    assert report2["selection_changed"] is True
    assert report2["applied_variant_key"] == "B"
    assert report2["selection_type"] == "stop_loss_forced_switch"
    assert report2["previous_variant_label"] == "룰 A 안정형"
    assert report2["previous_variant_profit_rate"] < 0
    assert report2["applied_variant_profit_rate"] > 0
    assert "손절이 발생하여" in report2["leader_reason"]

    # ── 시나리오 3: 평가 수익률은 양수(1%)이지만 거래 미완료(trade_count=0)이거나 realized_pnl이 없는 경우 (스위칭 차단) ──
    tester3 = DemoRuleVariantShadowTester()
    tester3._applied_variant_key = "A"
    tester3._initial_equity = 1_000_000.0

    tester3._portfolios["A"] = ShadowPortfolio(
        cash_balance=0.0,
        asset_balance=1000.0,
        avg_buy_price=1000.0,
        peak_equity=1_000_000.0,
        trade_count=1,
    )
    # B는 미실현 평가 자산 상승으로 profit_rate는 1%이나 trade_count가 0인 상태
    tester3._portfolios["B"] = ShadowPortfolio(
        cash_balance=0.0,
        asset_balance=1010.0,
        avg_buy_price=1000.0,
        peak_equity=1_010_000.0,
        trade_count=0,
        realized_pnl=0.0,
    )

    report3 = tester3.evaluate(
        decision=decision,
        current_price=900.0,
        portfolio=PortfolioState(
            cash_balance=1_000_000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
    )

    # 완결 거래(실현 손익)가 없으므로 B로 스위칭되지 않고 A 유지되어야 함
    assert report3["selection_changed"] is False
    assert report3["applied_variant_key"] == "A"


def test_demo_rule_variant_detects_stop_loss_even_when_position_is_fully_sold() -> None:
    tester = DemoRuleVariantShadowTester()
    tester._initial_equity = 1_000_000.0
    tester._portfolios["C"] = ShadowPortfolio(
        cash_balance=0.0,
        asset_balance=1000.0,
        avg_buy_price=1000.0,
        peak_equity=1_000_000.0,
    )

    report = tester.evaluate(
        decision=_decision(market_state="bear", buy_amount=0),
        current_price=900.0,
        portfolio=PortfolioState(
            cash_balance=1_000_000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
    )

    result = next(item for item in report["results"] if item["variant_key"] == "C")
    assert result["asset_balance"] == 0.0
    assert result["stop_loss_triggered_this_tick"] is True
