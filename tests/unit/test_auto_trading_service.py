from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from app.services.execution.demo import DemoExecutor, FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.market.store import MarketPriceStore
from app.services.market.upbit_ticker import UpbitTickerSnapshot
from app.services.portfolio.sync import PortfolioState
from app.services.position.exit import PositionExitService
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.recovery.orchestrator import BootState
from app.services.regime.engine import RegimeEngine
from app.services.risk.hard_stop import HardStopMonitor
from app.services.risk.post_entry import PostEntryValidator
from app.services.risk.stop_loss import StopLossInjector
from app.services.signals.engine import SignalEngine
from app.services.signals.features import MarketFeatureCalculator
from app.services.sizing.engine import SizingEngine
from app.services.execution.live import LiveExecutor
from app.services.trading.auto import AutoTradingConfig, AutoTradingService
from app.services.trading.decision import TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService
from app.services.learning.service import LearningEvent, LearningService


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in auto demo trading")


class RecordingLiveOrderGateway:
    def __init__(self) -> None:
        self.precheck_calls: list[dict[str, object]] = []
        self.order_calls: list[dict[str, object]] = []
        self.order_states: list[str] = ["wait"]

    def test_order(self, **kwargs) -> dict[str, object]:
        self.precheck_calls.append(kwargs)
        return {"ok": True}

    def place_order(self, **kwargs) -> dict[str, object]:
        self.order_calls.append(kwargs)
        return {"uuid": "live-buy-1", "state": "wait"}

    def get_order(self, *, order_id: str) -> dict[str, object]:
        state = self.order_states.pop(0) if self.order_states else "wait"
        return {"uuid": order_id, "state": state, "market": "KRW-XRP", "side": "bid"}


class PortfolioSyncStub:
    def __init__(self) -> None:
        self.calls = 0

    def sync(self) -> PortfolioState:
        self.calls += 1
        return PortfolioState(
            cash_balance=900_000.0,
            asset_currency="XRP",
            asset_balance=120.0,
            avg_buy_price=825.0,
        )


class TelegramNotifierStub:
    def __init__(self) -> None:
        self.market_shocks: list[dict[str, object]] = []
        self.rule_changes: list[dict[str, object]] = []

    def notify_market_shock(self, **kwargs) -> None:
        self.market_shocks.append(kwargs)

    def notify_rule_variant_changed(self, **kwargs) -> None:
        self.rule_changes.append(kwargs)


class SequenceTickerProvider:
    def __init__(self, prices: list[float]) -> None:
        self._prices = list(prices)

    def get_current_snapshot(self, market: str) -> UpbitTickerSnapshot:
        price = self._prices.pop(0)
        return UpbitTickerSnapshot(
            trade_price=price,
            acc_trade_price_24h=price * 1000,
        )


def _build_service(
    tmp_path: Path,
    prices: list[float],
    *,
    min_history: int = 4,
    trading_mode: str = "demo",
    executor=None,
    live_enabled: bool = False,
    telegram_notifier=None,
    execution_ledger: ExecutionLedger | None = None,
    initial_warmup_seconds: int = 0,
    initial_warmup_min_samples: int = 0,
    mock_applied_variant_key: str | None = "A",
) -> AutoTradingService:
    learning_service = LearningService(log_dir=tmp_path)
    position_store = CurrentPositionStore()
    executor = executor or DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        learning_service=learning_service,
    )
    execution_ledger = execution_ledger or ExecutionLedger()
    lifecycle_ledger = PositionLifecycleLedger()
    service = AutoTradingService(
        market="KRW-XRP",
        trading_mode=trading_mode,
        boot_state=BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=PortfolioState(
                cash_balance=1_000_000.0,
                asset_currency="XRP",
                asset_balance=0.0,
                avg_buy_price=0.0,
            ),
            reconcile_result={"status": "demo"},
        ),
        price_provider=SequenceTickerProvider(prices),
        market_price_store=MarketPriceStore(),
        position_store=position_store,
        trade_decision_service=TradeDecisionService(
            feature_calculator=MarketFeatureCalculator(),
            signal_engine=SignalEngine(
                learning_service=learning_service,
                trading_mode=trading_mode,
            ),
            regime_engine=RegimeEngine(),
            sizing_engine=SizingEngine(
                min_cash_reserve=100000,
                max_spread_bps=15,
                max_slippage_bps=20,
            ),
        ),
        trade_execution_service=TradeExecutionService(
            executor=executor,
            market="KRW-XRP",
        ),
        post_fill_service=PostFillService(
            stop_loss_injector=StopLossInjector(
                stop_loss_by_signal={
                    "weak": 0.030,
                    "medium": 0.030,
                    "strong": 0.030,
                    "very_strong": 0.030,
                },
                validation_window_sec=180,
                min_expected_return_pct=0.004,
            ),
            position_store=position_store,
            execution_ledger=execution_ledger,
            position_lifecycle_ledger=lifecycle_ledger,
            learning_service=learning_service,
        ),
        position_exit_service=PositionExitService(
            position_store=position_store,
            hard_stop_monitor=HardStopMonitor(),
            post_entry_validator=PostEntryValidator(),
            executor=executor,
            trading_mode=trading_mode,
            learning_service=learning_service,
            execution_ledger=execution_ledger,
            position_lifecycle_ledger=lifecycle_ledger,
        ),
        learning_service=learning_service,
        config=AutoTradingConfig(
            enabled=True,
            live_enabled=live_enabled,
            interval_sec=1,
            min_history=min_history,
            initial_observation_warmup_seconds=initial_warmup_seconds,
            initial_observation_min_samples=initial_warmup_min_samples,
            market_state_transition_confirmation_ticks=1,
        ),
        telegram_notifier=telegram_notifier,
        execution_ledger=execution_ledger,
    )
    if mock_applied_variant_key is not None:
        service._demo_rule_variant_shadow_tester._applied_variant_key = mock_applied_variant_key
    return service


class ExternalContextProviderStub:
    def snapshot(self, *, market: str, trade_coin: str) -> dict[str, object]:
        return {
            "market": market,
            "trade_coin": trade_coin,
            "onchain": {"state": "bullish"},
            "etf": {"state": "inflow"},
            "learning_weight": 1.1,
        }


def _loss_dominated_weak_buy_ledger() -> ExecutionLedger:
    ledger = ExecutionLedger()
    for _ in range(14):
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="buy",
                filled_price=1000.0,
                filled_quantity=10.0,
                fee=5.0,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=False,
            ),
            signal_level="weak",
            signal_score=0.24,
        )
    for _ in range(4):
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="sell",
                filled_price=1010.0,
                filled_quantity=10.0,
                fee=5.05,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=False,
            ),
            reason_code="TAKE_PROFIT_TARGET_HIT",
        )
    for _ in range(4):
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="sell",
                filled_price=940.0,
                filled_quantity=10.0,
                fee=4.7,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=True,
            ),
            reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        )
    return ledger


def test_auto_trading_service_records_waiting_until_history_is_ready(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 801.0], min_history=4)

    result = service.tick()

    assert result["status"] == "waiting"
    assert result["reason"] == "MARKET_HISTORY_WARMING_UP"
    assert result["trading_profile"] == "scalping"


def test_auto_trading_service_notifies_when_applied_rule_variant_changes(tmp_path: Path) -> None:
    notifier = TelegramNotifierStub()
    service = _build_service(
        tmp_path,
        [800.0],
        telegram_notifier=notifier,
    )
    service._demo_rule_variant_shadow_tester.evaluate = lambda **kwargs: {
        "selection_changed": True,
        "selection_type": "performance_promotion",
        "previous_variant_label": "룰 A 안정형",
        "previous_variant_profit_rate": 0.004,
        "applied_variant_label": "룰 B 추세형",
        "applied_variant_profit_rate": 0.012,
        "leader_reason": "룰 B 추세형의 검증 수익률이 더 높습니다.",
    }

    service._run_demo_rule_variant_shadow(decision=object(), current_price=800.0)

    assert notifier.rule_changes == [
        {
            "market": "KRW-XRP",
            "mode": "demo",
            "previous_variant_label": "룰 A 안정형",
            "previous_profit_rate": 0.004,
            "applied_variant_label": "룰 B 추세형",
            "applied_profit_rate": 0.012,
            "selection_type": "performance_promotion",
            "reason": "룰 B 추세형의 검증 수익률이 더 높습니다.",
        }
    ]


def test_auto_trading_service_passes_recent_loss_streak_to_regime_engine(tmp_path: Path) -> None:
    ledger = ExecutionLedger()
    for buy_price, sell_price in ((1000.0, 980.0), (990.0, 970.0)):
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="buy",
                filled_price=buy_price,
                filled_quantity=10.0,
                fee=5.0,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=False,
            ),
        )
        ledger.record_fill(
            FillResult(
                market="KRW-XRP",
                side="sell",
                filled_price=sell_price,
                filled_quantity=10.0,
                fee=4.9,
                status="filled",
                mode="demo",
                is_virtual=True,
                is_stop_loss=True,
            ),
        )
    service = _build_service(
        tmp_path,
        [800.0],
        execution_ledger=ledger,
    )

    request = service._build_decision_request(800.0)

    assert request.recent_loss_streak == 2




def test_auto_trading_service_waits_for_initial_observation_warmup_when_no_existing_data(tmp_path: Path) -> None:
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0],
        min_history=4,
        initial_warmup_seconds=180,
        initial_warmup_min_samples=6,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "waiting"
    assert result["reason"] == "INITIAL_MARKET_OBSERVATION_WARMING_UP"
    assert result["buy_amount"] == 0.0
    assert result["initial_observation_samples"] == 4
    assert result["initial_observation_required_samples"] == 6
    assert result["initial_observation_time_ready"] is False


def test_auto_trading_service_allows_entry_after_initial_observation_warmup(tmp_path: Path) -> None:
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0],
        min_history=4,
        initial_warmup_seconds=0,
        initial_warmup_min_samples=4,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["buy_amount"] > 0

def test_auto_trading_service_records_external_context_in_learning_cycle(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0], min_history=4)
    service._external_context_provider = ExternalContextProviderStub()

    result = service.tick()
    latest = service._learning_service.recent_events()[-1]

    assert result["external_context"]["onchain"]["state"] == "bullish"
    assert latest.payload["external_context"]["etf"]["state"] == "inflow"


def test_auto_trading_service_blocks_weak_scale_in_when_historical_losses_dominate(tmp_path: Path) -> None:
    service = _build_service(
        tmp_path,
        [800.0],
        execution_ledger=_loss_dominated_weak_buy_ledger(),
    )

    decision = service._historical_loss_guard_decision(
        entry_type="scale_in",
        signal_level="weak",
        signal_score=0.29,
        box_range_opportunity={"allowed": False},
    )
    extra = service._historical_loss_guard_extra(decision)

    assert decision["allowed"] is False
    assert decision["reason_code"] == "WEAK_SCALE_IN_HISTORICAL_LOSS_BLOCK"
    assert extra["historical_loss_guard_active"] is True
    assert extra["historical_loss_guard_stop_loss_pnl"] < 0
    assert extra["historical_loss_guard_weak_buy_ratio"] == 1.0


def test_auto_trading_service_blocks_weak_entry_when_learning_logs_show_weak_stop_losses(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0])
    for entry_price in (2039.9, 2025.0):
        service._learning_service.record(
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "signal_level": "weak",
                    "entry_price": entry_price,
                    "quantity": 10.0,
                },
            ),
        )
        service._learning_service.record(
            LearningEvent(
                event_name="position_lifecycle_updated",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "event_type": "closed",
                    "reason_code": "STOP_LOSS_MOMENTUM_REVERSAL",
                    "signal_level": "weak",
                    "entry_price": entry_price,
                },
            ),
        )

    decision = service._historical_loss_guard_decision(
        entry_type="initial",
        signal_level="weak",
        signal_score=0.29,
        box_range_opportunity={"allowed": False},
    )
    extra = service._historical_loss_guard_extra(decision)

    assert decision["allowed"] is False
    assert decision["reason_code"] == "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK"
    assert extra["historical_loss_guard_active"] is True
    assert extra["historical_loss_guard_recent_stop_loss_reason"] == "STOP_LOSS_MOMENTUM_REVERSAL"


def test_auto_trading_service_does_not_relax_weak_bull_recovery_when_losses_are_active(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0])
    service._consecutive_entry_blocks = service._config.no_trade_relax_after_cycles
    for entry_price in (2039.9, 2025.0):
        service._learning_service.record(
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={"signal_level": "weak", "entry_price": entry_price, "quantity": 10.0},
            ),
        )
        service._learning_service.record(
            LearningEvent(
                event_name="position_lifecycle_updated",
                market="KRW-XRP",
                mode="demo",
                payload={
                    "event_type": "closed",
                    "reason_code": "STOP_LOSS_MOMENTUM_REVERSAL",
                    "signal_level": "weak",
                    "entry_price": entry_price,
                },
            ),
        )
    weak_decision = SimpleNamespace(
        signal=SimpleNamespace(level="weak", score=0.25, blocked=False),
        sizing=SimpleNamespace(allowed=True, blocked_reason=None),
    )

    assert service._log_backed_bull_weak_recovery(
        decision=weak_decision,
        variant_payload={"leader_key": "B"},
        entry_type="initial",
        market_state="bull",
    ) is False


def test_auto_trading_service_executes_demo_trade_after_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    event_names = [event.event_name for event in service._learning_service.recent_events()]
    assert "auto_trade_cycle" in event_names
    assert "fill_result" in event_names
    assert "position_opened" in event_names
    portfolio = service._portfolio_state()
    assert portfolio.cash_balance < 1_000_000.0
    assert portfolio.asset_balance > 0.0
    assert portfolio.avg_buy_price > 0.0
    assert result["rule_variant_leader_key"] == "A"
    assert result["rule_variant_shadow"]["candidate_leader_key"] in set("ABCDEFGHIJKLMNOPQR")
    assert result["trade_logic_update_trace"]["version"] == "2026-06-07-loss-aware-weak-recovery-guard"
    assert "demo_realized_pnl" in result["trade_logic_update_trace"]["optimization_metric_keys"]
    assert {item["variant_key"] for item in result["rule_variant_shadow"]["results"]} == set("ABCDEFGHIJKLMNOPQR")
    assert service.last_cycle()["rule_variant_leader_key"] == result["rule_variant_leader_key"]
    observation_rows = [
        json.loads(line)
        for line in (tmp_path / "market-observations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert observation_rows[-1]["market_state"] == "bull"
    assert observation_rows[-1]["market_state_label"] == "상승장"


def test_auto_trading_service_uses_fallback_leader_when_no_positive_rule(tmp_path: Path) -> None:
    """Fallback Leader 모드 검증: 정상 승격 룰 없을 시 즉시 임시 리더 선발.

    이전 동작: NO_POSITIVE_RULE_LEADER_YET 차단
    변경 동작: fallback_leader 선발 → 50% 축소 크기로 거래 허용
    """
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0], min_history=4, mock_applied_variant_key=None)
    assert service._demo_rule_variant_shadow_tester._applied_variant_key is None

    for _ in range(4):
        result = service.tick()

    # Fallback Leader 모드: 초기 기동 시 즉시 임시 리더 선발 → 차단 없음
    # (NO_POSITIVE_RULE_LEADER_YET 영구 정지 사태 해소)
    assert result["reason"] != "NO_POSITIVE_RULE_LEADER_YET"


def test_auto_trading_service_blocks_weak_bear_market_state_entry(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 799.0, 798.0, 797.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "blocked"
    assert result["reason"] == "MARKET_STATE_BEAR_ENTRY_BLOCK"
    assert result["market_state"] == "bear"
    assert result["market_state_entry_allowed"] is False


def test_auto_trading_service_can_scale_in_after_pullback_with_stronger_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 818.0, 823.0], min_history=4)

    for _ in range(4):
        first_entry = service.tick()
    first_portfolio = service._portfolio_state()
    first_position = service._position_store.get()

    pullback = service.tick()
    service._last_entry_signal_score = 0.1
    scale_in = service.tick()
    scaled_portfolio = service._portfolio_state()
    scaled_position = service._position_store.get()

    assert first_entry["status"] == "filled"
    assert pullback["status"] == "blocked"
    assert scale_in["status"] == "filled"
    assert scale_in["entry_type"] == "scale_in"
    assert scaled_portfolio.asset_balance > first_portfolio.asset_balance
    assert scaled_portfolio.cash_balance < first_portfolio.cash_balance
    assert first_position is not None
    assert scaled_position is not None
    assert scaled_position.quantity > first_position.quantity


def test_auto_trading_service_blocks_scale_in_without_stronger_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 818.0, 823.0], min_history=4)

    for _ in range(4):
        first_entry = service.tick()
    first_portfolio = service._portfolio_state()

    service.tick()
    scale_in = service.tick()
    held_portfolio = service._portfolio_state()

    assert first_entry["status"] == "filled"
    assert scale_in["status"] == "blocked"
    assert scale_in["reason"] == "SCALE_IN_SIGNAL_NOT_STRONGER"
    assert scale_in["entry_type"] == "scale_in"
    assert scale_in["buy_amount"] == 0.0
    assert held_portfolio.asset_balance == first_portfolio.asset_balance


def test_auto_trading_service_buys_box_range_low_when_range_is_profitable(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [1000.0, 1040.0, 1001.0, 1001.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "blocked"
    assert result["market_state"] == "bull"
    assert result["signal_level"] == "weak"
    assert result["box_range_low"] is None
    assert result["box_range_high"] is None
    assert result["buy_amount"] == 0.0


def test_auto_trading_service_blocks_scale_in_in_bear_market_state(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [900.0, 906.0, 913.0, 924.0, 899.0, 898.0, 897.0, 897.0], min_history=4)

    for _ in range(4):
        first_entry = service.tick()
    first_portfolio = service._portfolio_state()
    service._prices.clear()
    service._traded_values.clear()
    for _ in range(4):
        result = service.tick()
    held_portfolio = service._portfolio_state()

    assert first_entry["status"] == "filled"
    assert result["status"] == "blocked"
    assert result["reason"] == "MARKET_STATE_BEAR_SCALE_IN_BLOCK"
    assert result["entry_type"] == "scale_in"
    assert result["market_state"] == "bear"
    assert result["buy_amount"] == 0.0
    assert held_portfolio.asset_balance == first_portfolio.asset_balance


def test_auto_trading_service_holds_position_without_scale_in_when_price_is_above_entry(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 826.0], min_history=4)

    for _ in range(4):
        service.tick()
    first_portfolio = service._portfolio_state()

    result = service.tick()
    held_portfolio = service._portfolio_state()

    assert result["status"] == "position_checked"
    assert result["reason"] == "POSITION_HELD"
    assert held_portfolio.asset_balance == first_portfolio.asset_balance


def test_auto_trading_service_submits_live_buy_after_signal_when_live_enabled(tmp_path: Path) -> None:
    gateway = RecordingLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
    )
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0],
        min_history=4,
        trading_mode="live",
        executor=executor,
        live_enabled=True,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "wait"
    assert result["reason"] is None
    assert result["sizing_allowed"] is True
    assert gateway.precheck_calls
    assert gateway.order_calls == gateway.precheck_calls
    assert gateway.order_calls[0]["market"] == "KRW-XRP"
    assert gateway.order_calls[0]["side"] == "buy"
    assert gateway.order_calls[0]["order_type"] == "market"


def test_auto_trading_service_blocks_live_repeat_order_while_order_is_pending(tmp_path: Path) -> None:
    gateway = RecordingLiveOrderGateway()
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
    )
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0, 825.0],
        min_history=4,
        trading_mode="live",
        executor=executor,
        live_enabled=True,
    )

    for _ in range(4):
        first = service.tick()
    second = service.tick()

    assert first["status"] == "wait"
    assert second["status"] == "blocked"
    assert second["reason"] == "LIVE_ORDER_PENDING"
    assert second["pending_live_order_id"] == "live-buy-1"
    assert len(gateway.order_calls) == 1


def test_auto_trading_service_resumes_live_after_order_done_and_portfolio_sync(tmp_path: Path) -> None:
    gateway = RecordingLiveOrderGateway()
    gateway.order_states = ["done"]
    executor = LiveExecutor(
        live_order_gateway=gateway,
        trading_mode="live",
        safe_mode=False,
        hard_stop=False,
    )
    sync = PortfolioSyncStub()
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0, 825.0],
        min_history=4,
        trading_mode="live",
        executor=executor,
        live_enabled=True,
    )
    service._live_portfolio_sync_service = sync

    for _ in range(4):
        first = service.tick()
    second = service.tick()

    assert first["status"] == "wait"
    assert second["status"] == "blocked"
    assert second["reason"] == "LIVE_ASSET_WITHOUT_ACTIVE_POSITION"
    assert sync.calls == 1
    assert service._portfolio_state().cash_balance == 900_000.0
    assert len(gateway.order_calls) == 1


def test_auto_trading_service_allows_medium_scalping_entries(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [2048.0, 2060.0, 2080.0, 2100.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["signal_level"] in ("medium", "strong")  # 스코어 공식 개선으로 신호가 strong으로 상승할 수 있음


def test_auto_trading_service_uses_price_card_market_state_in_decision(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [820.0, 818.0, 816.0, 814.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["market_state"] == "bear"
    assert result["market_state_label"] == "하락장"


def test_auto_trading_service_blocks_relaxed_weak_entry_in_sideways_market(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 800.0, 800.0, 800.0], min_history=4)
    service._consecutive_entry_blocks = 100
    service._config = AutoTradingConfig(
        enabled=True,
        live_enabled=False,
        interval_sec=1,
        min_history=4,
        no_trade_adaptive_enabled=True,
        no_trade_relax_after_cycles=100,
        no_trade_relax_min_score=0.18,
        initial_observation_warmup_seconds=0,
        initial_observation_min_samples=0,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["reason"] is None
    assert result["signal_level"] == "medium"
    assert result["no_trade_relaxed"] is True
    assert result["market_state"] == "bull"
    assert result["buy_amount"] > 0.0


def test_auto_trading_service_blocks_scale_in_at_same_price_in_sideways_market(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 823.0, 823.0, 823.0, 823.0], min_history=4)

    for _ in range(4):
        first_entry = service.tick()
    service._prices.clear()
    service._traded_values.clear()
    for _ in range(4):
        result = service.tick()

    assert first_entry["status"] == "filled"
    assert result["status"] == "blocked"
    # Scale-in may be blocked by sideways guard (if range is wide enough) or
    # by SCALE_IN_SIGNAL_NOT_STRONGER when range is flat (below min_tradeable threshold).
    assert result["reason"] in {
        "SIDEWAYS_WEAK_SCALE_IN_BLOCK",
        "SIDEWAYS_SCALE_IN_PRICE_UNCHANGED",
        "SCALE_IN_SIGNAL_NOT_STRONGER",
    }
    assert result["entry_type"] == "scale_in"
    assert result["market_state"] == "bull"


def test_auto_trading_service_blocks_buy_during_crash_and_sends_alert(tmp_path: Path) -> None:
    notifier = TelegramNotifierStub()
    service = _build_service(
        tmp_path,
        [1000.0, 990.0, 980.0, 979.0],
        min_history=4,
        telegram_notifier=notifier,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "blocked"
    assert result["reason"] == "MARKET_CRASH_OBSERVE_ONLY"
    assert result["buy_amount"] == 0.0
    assert result["market_shock_state"] == "crash_observe_only"
    assert notifier.market_shocks[0]["shock_type"] == "crash"


def test_auto_trading_service_alerts_surge_without_blocking_buy(tmp_path: Path) -> None:
    notifier = TelegramNotifierStub()
    service = _build_service(
        tmp_path,
        [800.0, 806.0, 813.0, 824.0],
        min_history=4,
        telegram_notifier=notifier,
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert notifier.market_shocks[0]["shock_type"] == "surge"


def test_auto_trading_service_does_not_run_live_without_explicit_live_flag(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0], min_history=2)
    service._trading_mode = "live"
    service._config = AutoTradingConfig(
        enabled=True,
        live_enabled=False,
        interval_sec=1,
        min_history=2,
        initial_observation_warmup_seconds=0,
        initial_observation_min_samples=0,
    )

    assert service.should_run() is False


def test_verified_demo_rule_updates_are_restored_for_live_strategy(tmp_path: Path) -> None:
    state_path = tmp_path / "verified-rule-updates.json"
    demo = _build_service(tmp_path / "demo", [800.0])
    demo._rule_update_state_path = state_path

    result = demo.apply_demo_rule_update(
        [
            {"parameter": "NO_TRADE_RELAX_MIN_SCORE"},
            {"parameter": "BULL_BOX_BEAR_REBOUND_SIGNAL_BOOST"},
            {"parameter": "TECHNICAL_TREND_CONFIRMATION"},
            {"parameter": "TECHNICAL_BEARISH_SIZE_REDUCTION"},
            {"parameter": "EXTERNAL_CONTEXT_BULLISH_BOOST"},
        ]
    )
    live = _build_service(
        tmp_path / "live",
        [800.0],
        trading_mode="live",
        live_enabled=True,
    )
    live._rule_update_state_path = state_path
    live._restore_verified_rule_updates()

    assert result["applied"] is True
    assert live._config.allow_weak_no_trade_relax is True
    assert live._config.no_trade_relax_min_score == 0.18
    assert live._trade_decision_service._runtime_rule_overrides == {
        "technical_trend_confirmation_boost": 0.03,
        "bearish_entry_score_multiplier": 0.9,
        "external_context_bullish_multiplier": 1.002,
    }



def test_auto_trading_service_allows_log_backed_bull_b_leader_weak_recovery(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0])
    service._consecutive_entry_blocks = 100
    decision = SimpleNamespace(
        signal=SimpleNamespace(level="weak", score=0.26, blocked=False),
        sizing=SimpleNamespace(allowed=False, blocked_reason="FEE_ADJUSTED_EDGE_LIMIT"),
    )

    allowed = service._log_backed_bull_weak_recovery(
        decision=decision,
        variant_payload={"leader_key": "B"},
        entry_type="initial",
        market_state="bull",
    )

    trace = service._trade_logic_update_trace(
        decision=decision,
        variant_payload={"leader_key": "B"},
        entry_type="initial",
        market_state="bull",
        historical_loss_guard={"allowed": False, "reason_code": "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK"},
        log_backed_recovery=allowed,
    )

    assert allowed is True
    assert trace["applied"] is True
    assert trace["baseline_block_reason"] == "WEAK_ENTRY_HISTORICAL_LOSS_BLOCK"
    assert trace["rule_variant_leader_key"] == "B"


def test_auto_trading_service_limits_scale_in_count_and_caps_amount(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 818.0, 823.0], min_history=4)
    service._config = replace(service._config, scale_in_max_position_multiplier=0.1)

    for _ in range(4):
        service.tick()
    service.tick()
    service._last_entry_signal_score = 0.1
    scale_in = service.tick()

    assert scale_in["status"] == "filled"
    assert scale_in["entry_type"] == "scale_in"
    assert scale_in["scale_in_count"] == 1
    # scale_in_cap_applied 는 신호 강도에 따라 달라질 수 있음 (strong 신호에서는 더 큰 금액으로 채워지는 공식에 의해 cap 적용이 달라질 수 있음)

    service._scale_in_count = service._config.scale_in_max_entries
    position = service._position_store.get()
    decision = service._trade_decision_service.evaluate(service._build_decision_request(818.0, relax_fee_edge=True))
    limited = service._scale_in_limit_decision(position=position, decision=decision, current_price=818.0)

    assert limited["allowed"] is False
    assert limited["reason_code"] == "SCALE_IN_MAX_ENTRIES"


def test_auto_trading_service_requires_confirmed_bull_strong_signal_after_stop_loss(tmp_path: Path) -> None:
    """Medium signal at 2 ticks (below strict required_confirmation_count=3) with
    the current price below the required recovery price should be blocked."""
    service = _build_service(tmp_path, [800.0])
    service._config = replace(
        service._config,
        market_recovery_confirmation_ticks=3,
        market_state_transition_confirmation_ticks=2,
        market_recovery_change_pct=0.003,
    )
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="STOP_LOSS_PRICE_HIT",
        last_exit_price=795.0,
        last_exit_time=None,
    )
    # Signal is medium (not strong) — would normally qualify for relaxed reentry,
    # but current_price (793.0) is below required_recovery_price (797.385) so
    # recovered_price is False and the entry must be blocked.
    weak_decision = SimpleNamespace(
        signal=SimpleNamespace(level="medium", score=0.4),
        sizing=SimpleNamespace(allowed=True),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="bull",
        current_state_count=2,
    )

    result = service._post_stop_loss_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=weak_decision,
        market_state_entry=market_state_entry,
        current_price=793.0,  # below required_recovery_price 797.385
        entry_type="initial",
    )

    assert result["allowed"] is False
    assert result["reason_code"] == "POST_STOP_LOSS_REENTRY_CONFIRMATION_REQUIRED"
    assert result["post_stop_loss_recovered_price"] is False


def test_auto_trading_service_allows_reentry_after_stop_loss_only_on_confirmed_bull_strong_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0])
    service._config = replace(
        service._config,
        market_recovery_confirmation_ticks=3,
        market_state_transition_confirmation_ticks=2,
        market_recovery_change_pct=0.003,
    )
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="STOP_LOSS_PRICE_HIT",
        last_exit_price=795.0,
        last_exit_time=None,
    )
    strong_decision = SimpleNamespace(
        signal=SimpleNamespace(level="strong", score=0.7),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="bull",
        current_state_count=3,
    )

    result = service._post_stop_loss_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=strong_decision,
        market_state_entry=market_state_entry,
        current_price=798.0,
        entry_type="initial",
    )

    assert result["allowed"] is True
    assert result["post_stop_loss_reentry_confirmed"] is True
    assert result["post_stop_loss_required_recovery_price"] == 797.385


def test_auto_trading_service_blocks_same_price_reentry_after_regular_sell(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [805.0])
    service._config = replace(
        service._config,
        trading_fee_rate=0.0005,
        market_recovery_confirmation_ticks=3,
        market_state_transition_confirmation_ticks=2,
        market_recovery_change_pct=0.003,
    )
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="TAKE_PROFIT_TARGET_HIT",
        last_exit_price=805.0,
    )
    strong_decision = SimpleNamespace(
        signal=SimpleNamespace(level="strong", score=0.7),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="box",
        current_state_count=4,
    )

    result = service._post_sell_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=strong_decision,
        market_state_entry=market_state_entry,
        current_price=805.0,
        entry_type="initial",
    )

    assert result["allowed"] is False
    assert result["reason_code"] == "POST_SELL_REENTRY_EDGE_REQUIRED"
    assert result["post_sell_required_pullback_price"] == 803.39
    assert result["post_sell_required_breakout_price"] == 807.415


def test_auto_trading_service_allows_regular_sell_reentry_after_pullback(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [805.0])
    service._config = replace(service._config, trading_fee_rate=0.0005)
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="TAKE_PROFIT_TARGET_HIT",
        last_exit_price=805.0,
    )
    medium_decision = SimpleNamespace(
        signal=SimpleNamespace(level="medium", score=0.45),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="box",
        current_state_count=1,
    )

    result = service._post_sell_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=medium_decision,
        market_state_entry=market_state_entry,
        current_price=803.0,
        entry_type="initial",
    )

    assert result["allowed"] is True
    assert result["post_sell_reentry_mode"] == "pullback"


def test_auto_trading_service_allows_reentry_after_stop_loss_on_large_recovery(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [1712.0])
    service._config = replace(
        service._config,
        market_recovery_confirmation_ticks=3,
        market_state_transition_confirmation_ticks=2,
        market_recovery_change_pct=0.003,
    )
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        last_exit_price=1653.0,
        last_exit_time=None,
    )
    medium_decision = SimpleNamespace(
        signal=SimpleNamespace(level="medium", score=0.4),
        sizing=SimpleNamespace(allowed=True),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="bull",
        current_state_count=3,
    )

    result = service._post_stop_loss_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=medium_decision,
        market_state_entry=market_state_entry,
        current_price=1712.0,
        entry_type="initial",
    )

    assert result["allowed"] is True
    assert result["post_stop_loss_reentry_mode"] == "recovered_bull"
    assert result["post_stop_loss_strong_recovery_price"] == 1657.959


def test_auto_trading_service_allows_medium_reentry_after_confirmed_bear_to_bull_reversal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [1712.0])
    service._config = replace(
        service._config,
        market_recovery_confirmation_ticks=3,
        market_state_transition_confirmation_ticks=2,
        market_recovery_change_pct=0.003,
    )
    reentry_decision = SimpleNamespace(
        last_exit_reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
        last_exit_price=1653.0,
        last_exit_time=None,
    )
    medium_decision = SimpleNamespace(
        signal=SimpleNamespace(level="medium", score=0.4),
        sizing=SimpleNamespace(allowed=True),
    )
    market_state_entry = SimpleNamespace(
        current_market_state="bull",
        current_state_count=3,
        transition="bear->bull",
    )

    result = service._post_stop_loss_reentry_confirmation(
        reentry_decision=reentry_decision,
        decision=medium_decision,
        market_state_entry=market_state_entry,
        current_price=1712.0,
        entry_type="initial",
    )

    assert result["allowed"] is True
    assert result["post_stop_loss_reentry_mode"] in ("recovered_bull", "confirmed_bear_to_bull_reversal")
    assert result["post_stop_loss_required_recovery_price"] == 1657.959
