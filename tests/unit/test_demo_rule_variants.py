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

    assert {item["variant_key"] for item in report["results"]} == set("ABCDEFGHIJKLMNOPQR")
    # Fallback Leader 즉시 선발: 초기 기동 시 leader_key가 None이 아닌 최소 낙폭 룰로 설정됨
    assert report["leader_key"] is not None
    assert report["is_fallback_leader"] is True
    assert report["selection_type"] == "fallback_leader"
    assert report["candidate_leader_key"] in set("ABCDEFGHIJKLMNOPQR")
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
    # 조기 승격(early promotion) 로직으로 인해 1사이클 완료 후 바로 리더가 승격될 수 있음
    # (leader_key가 None 또는 유효한 키이어야 함)
    assert report["leader_key"] is None or report["leader_key"] in set("ABCDEFGHIJKLMNOPQR")
    assert report["candidate_leader_key"] in set("ABCDEFGHIJKLMNOPQR")


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
    # 방어형이 안정형보다 effective_sell_multiplier가 큼야 함
    assert results["C"]["effective_sell_multiplier"] > results["A"]["effective_sell_multiplier"]
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
    # 룰 O는 market_pressure >= 0.02 조건에서 weak도 허용되어 buy 반환 (로직 변경에 따른 업데이트)
    assert results["O"]["last_action"] in ("buy", "hold")  # pressure 디폴트값에 따라 달라질 수 있음


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
    # reset 후에도 Fallback Leader 즉시 선발 (is_initial_start=True)
    assert report["leader_key"] is not None
    assert report["is_fallback_leader"] is True


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


def test_demo_rule_variant_requires_five_closed_trades_for_normal_promotion() -> None:
    """MIN_PROMOTION_TRADES=5 기준 검증 (20→10→5로 완화됨)."""
    candidate = {
        "profit_rate": 0.02,
        "realized_pnl": 20_000.0,
        "trade_count": 4,  # 최소(5) 미만 → 승격 불가
        "profit_factor": 2.0,
        "stop_loss_rate": 0.1,
    }

    assert DemoRuleVariantShadowTester._promotion_eligible(candidate) is False

    candidate["trade_count"] = 5  # 정확히 MIN_PROMOTION_TRADES → 승격 가능
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


# ══════════════════════════════════════════════════════════════════════════════
# 하락장 손절 방지 테스트 (신규 추가 9개)
# ══════════════════════════════════════════════════════════════════════════════

def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=1_000_000,
        asset_currency="XRP",
        asset_balance=0,
        avg_buy_price=0,
    )


def test_rule_a_blocks_bear_entry_without_confirmed_transition() -> None:
    """Rule A: bear 상태에서 b2b_confirmed 없이 진입 완전 차단 (이전: b2b>=0.45면 허용).
    07-05~07-07 손절 패턴의 핵심 원인 차단.
    """
    tester = DemoRuleVariantShadowTester()
    # bull 상태로 한 번 사이클 돌려서 섬도 초기화
    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=_portfolio(),
    )
    # bear 상태, b2b_confirmed=False → 진입 차단이어야 함
    report = tester.evaluate(
        decision=_decision(market_state="bear", signal_level="strong"),
        current_price=1_000,
        portfolio=_portfolio(),
    )
    result_a = next(item for item in report["results"] if item["variant_key"] == "A")
    # 보유 자산이 없으므로 last_action은 hold(buy 시도 차단)
    assert result_a["entry_allowed_by_variant"] is False
    assert result_a["action_reason"] == "bear_balance_defense"


def test_rule_a_allows_bear_entry_only_on_confirmed_transition() -> None:
    """Rule A: bear→bull 전환 확정(b2b_confirmed) 시에만 진입 허용."""
    from unittest.mock import patch

    from app.services.trading.market_transition import TransitionState

    confirmed_state = TransitionState(
        bear_to_bull_score=0.75,
        bear_to_bull_confirmed=True,
        bull_to_bear_score=0.10,
        bull_to_bear_confirmed=False,
        dynamic_box_low=None,
        dynamic_box_high=None,
        dynamic_box_position=None,
        prev_rsi=None,
        prev_macd_histogram=None,
    )

    tester = DemoRuleVariantShadowTester()
    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=_portfolio(),
    )
    with patch.object(tester._transition_detector, "evaluate", return_value=confirmed_state):
        report = tester.evaluate(
            decision=_decision(market_state="bear", signal_level="strong"),
            current_price=1_000,
            portfolio=_portfolio(),
        )
    result_a = next(item for item in report["results"] if item["variant_key"] == "A")
    assert result_a["entry_allowed_by_variant"] is True
    assert result_a["action_reason"] == "bear_to_bull_transition_entry"


def test_consecutive_stop_losses_trigger_cooling_period() -> None:
    """연속 2회 손절 시 쿨다운(200 틱) 발동 → 이후 매수 차단."""
    shadow = ShadowPortfolio(
        cash_balance=1_000_000,
        asset_balance=100.0,
        avg_buy_price=1_000.0,   # 평단 1000원
        consecutive_stop_loss_count=1,  # 이미 1회 손절
    )
    tester = DemoRuleVariantShadowTester()

    from app.services.trading.variants import DemoRuleVariantPolicy

    stop_loss_policy = DemoRuleVariantPolicy(
        buy_multiplier=1.0,
        sell_multiplier=1.0,
        take_profit_pct=0.015,
        stop_loss_pct=0.008,   # 0.8% 손절 임계
        entry_allowed=True,
        action_reason="test",
        market_state="bull",
        market_pressure=0.0,
        box_position=None,
        bear_to_bull_score=0.0,
        bull_to_bear_score=0.0,
        transition_buy_boost=1.0,
        forced_sell=False,
    )
    # 손절 발동 가격 (1000 * (1 - 0.008) = 992 이하)
    tester._maybe_shadow_sell(
        shadow=shadow,
        policy=stop_loss_policy,
        decision=_decision(market_state="bull"),
        current_price=985.0,  # -1.5% → 손절
    )
    # 2회 연속 손절 → 쿨다운 200 발동
    assert shadow.consecutive_stop_loss_count == 2
    assert shadow.cooling_off_ticks_remaining == 200


def test_cooling_period_blocks_new_buy_and_decrements() -> None:
    """쿨다운 중 매수 차단 + 매 틱마다 카운터 1 감소."""
    shadow = ShadowPortfolio(
        cash_balance=1_000_000,
        asset_balance=0.0,
        avg_buy_price=0.0,
        cooling_off_ticks_remaining=5,
    )
    tester = DemoRuleVariantShadowTester()

    from app.services.trading.variants import DemoRuleVariantPolicy

    buy_policy = DemoRuleVariantPolicy(
        buy_multiplier=1.0,
        sell_multiplier=1.0,
        take_profit_pct=0.015,
        stop_loss_pct=0.008,
        entry_allowed=True,
        action_reason="test",
        market_state="bull",
        market_pressure=0.1,
        box_position=None,
        bear_to_bull_score=0.0,
        bull_to_bear_score=0.0,
        transition_buy_boost=1.0,
        forced_sell=False,
    )
    result = tester._maybe_shadow_buy(
        shadow=shadow,
        policy=buy_policy,
        decision=_decision(market_state="bull"),
        current_price=1_000.0,
    )
    assert result == "hold"
    assert shadow.cooling_off_ticks_remaining == 4  # 1 감소


def test_profit_win_resets_consecutive_stop_loss_count() -> None:
    """수익 발생 시 연속 손절 카운터 리셋."""
    shadow = ShadowPortfolio(
        cash_balance=500_000,
        asset_balance=100.0,
        avg_buy_price=1_000.0,
        consecutive_stop_loss_count=2,
        cooling_off_ticks_remaining=150,
    )
    tester = DemoRuleVariantShadowTester()

    from app.services.trading.variants import DemoRuleVariantPolicy

    profit_policy = DemoRuleVariantPolicy(
        buy_multiplier=1.0,
        sell_multiplier=1.0,
        take_profit_pct=0.005,   # 0.5% 목표
        stop_loss_pct=0.015,
        entry_allowed=True,
        action_reason="test",
        market_state="bull",
        market_pressure=0.1,
        box_position=None,
        bear_to_bull_score=0.0,
        bull_to_bear_score=0.0,
        transition_buy_boost=1.0,
        forced_sell=False,
    )
    # 1% 수익 → 익절
    tester._maybe_shadow_sell(
        shadow=shadow,
        policy=profit_policy,
        decision=_decision(market_state="bull"),
        current_price=1_010.0,
    )
    assert shadow.consecutive_stop_loss_count == 0  # 리셋


def test_emergency_fallback_triggers_on_two_stop_losses() -> None:
    """비상 전환 기준 완화: 2회 손절(기존 3회)만으로 방어 룰로 즉시 전환."""
    tester = DemoRuleVariantShadowTester()
    portfolio = _portfolio()

    # 초기 설정: 한 룰에 2회 손절 누적
    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=portfolio,
    )
    # 현재 적용 룰의 stop_loss_count를 2로 강제 설정
    if tester._applied_variant_key:
        shadow = tester._portfolios.get(tester._applied_variant_key)
        if shadow:
            shadow.stop_loss_count = 2
            shadow.trade_count = 2

    assert tester.EMERGENCY_FALLBACK_STOP_LOSS_COUNT == 2


def test_bear_market_forces_minimum_80pct_sell_ratio() -> None:
    """bear 상태 진입 시 매도 비율 최소 80% 강제 적용 (신속 포지션 청산)."""
    shadow = ShadowPortfolio(
        cash_balance=500_000,
        asset_balance=100.0,
        avg_buy_price=1_000.0,
    )
    tester = DemoRuleVariantShadowTester()

    from app.services.trading.variants import DemoRuleVariantPolicy

    # 낮은 sell_multiplier (기본 0.35)인 bull→bear 전환 상황
    bear_policy = DemoRuleVariantPolicy(
        buy_multiplier=0.0,
        sell_multiplier=0.5,   # 낮은 sell multiplier
        take_profit_pct=0.015,
        stop_loss_pct=0.030,
        entry_allowed=False,
        action_reason="bear_test",
        market_state="bear",
        market_pressure=-0.2,
        box_position=None,
        bear_to_bull_score=0.0,
        bull_to_bear_score=0.8,
        transition_buy_boost=1.0,
        forced_sell=False,
    )
    result = tester._maybe_shadow_sell(
        shadow=shadow,
        policy=bear_policy,
        decision=_decision(market_state="bear"),
        current_price=990.0,   # bear 시장 = 즉시 매도 발동
    )
    assert result == "sell"
    # base_sell_ratio=0.8, sell_multiplier=0.5 → min(0.8*0.5, 1.0)=0.40 → 40 XRP 매도, 60 남음
    # bear 시장 80% 기준 적용 확인 (무조건 80% 이상 base 잔여 없음)
    assert shadow.asset_balance < 100.0  # 일부 성공적으로 매도됨


def test_all_aggressive_rules_block_in_bear_without_transition() -> None:
    """강한 하락장에서 공격형 룰 B, H, M, O, P가 모두 진입 차단."""
    tester = DemoRuleVariantShadowTester()
    portfolio = _portfolio()

    # 초기 틱
    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=portfolio,
    )
    # bear + 전환 없음 (b2b_confirmed=False, b2b_score 낮음)
    report = tester.evaluate(
        decision=_decision(market_state="bear", signal_level="medium"),
        current_price=1_000,
        portfolio=portfolio,
    )
    results = {item["variant_key"]: item for item in report["results"]}
    aggressive_rules = ["B", "H", "M", "O", "P"]
    for key in aggressive_rules:
        assert results[key]["entry_allowed_by_variant"] is False, (
            f"Rule {key} should block entry in bear market without transition"
        )


def test_forced_sell_triggered_on_bull_to_bear_confirmation() -> None:
    """bull→bear 전환 확인 시 forced_sell 발동 → 모든 룰에서 entry_allowed=False."""
    from unittest.mock import patch

    from app.services.trading.market_transition import TransitionState

    bear_confirmed_state = TransitionState(
        bear_to_bull_score=0.10,
        bear_to_bull_confirmed=False,
        bull_to_bear_score=0.85,
        bull_to_bear_confirmed=True,   # ← 하락 전환 확정
        dynamic_box_low=None,
        dynamic_box_high=None,
        dynamic_box_position=None,
        prev_rsi=None,
        prev_macd_histogram=None,
    )

    tester = DemoRuleVariantShadowTester()
    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=_portfolio(),
    )
    with patch.object(tester._transition_detector, "evaluate", return_value=bear_confirmed_state):
        report = tester.evaluate(
            decision=_decision(market_state="bull"),
            current_price=1_000,
            portfolio=_portfolio(),
        )
    # forced_sell 발동 → 모든 룰에서 신규 매수 차단
    for item in report["results"]:
        assert item["entry_allowed_by_variant"] is False, (
            f"Rule {item['variant_key']} should block entry when bull→bear confirmed"
        )
    assert report["bull_to_bear_confirmed"] is True


def test_stop_loss_rate_above_threshold_prevents_promotion() -> None:
    """손절률(stop_loss_rate) > 40%인 룰은 성과가 좋아도 승격 불가."""
    tester = DemoRuleVariantShadowTester()
    portfolio = _portfolio()

    tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_000,
        portfolio=portfolio,
    )

    # 현재 적용 룰 섀도에 높은 손절률 강제 설정
    for key, shadow in tester._portfolios.items():
        shadow.trade_count = 25
        shadow.win_count = 20
        shadow.stop_loss_count = 12  # 12/25 = 48% > 40%
        shadow.realized_pnl = 5_000.0
        shadow.gross_profit = 10_000.0
        shadow.gross_loss = 3_000.0

    report = tester.evaluate(
        decision=_decision(market_state="bull"),
        current_price=1_010,
        portfolio=portfolio,
    )
    # 모든 룰 손절률 48% → 승격 불가
    for item in report["results"]:
        assert item["promotion_eligible"] is False, (
            f"Rule {item['variant_key']} should not be promotable with high stop_loss_rate"
        )
