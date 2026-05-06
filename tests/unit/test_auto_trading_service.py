from __future__ import annotations

from pathlib import Path

from app.services.execution.demo import DemoExecutor
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
from app.services.learning.service import LearningService


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in auto demo trading")


class RecordingLiveOrderGateway:
    def __init__(self) -> None:
        self.precheck_calls: list[dict[str, object]] = []
        self.order_calls: list[dict[str, object]] = []

    def test_order(self, **kwargs) -> dict[str, object]:
        self.precheck_calls.append(kwargs)
        return {"ok": True}

    def place_order(self, **kwargs) -> dict[str, object]:
        self.order_calls.append(kwargs)
        return {"uuid": "live-buy-1", "state": "wait"}


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
) -> AutoTradingService:
    learning_service = LearningService(log_dir=tmp_path)
    position_store = CurrentPositionStore()
    executor = executor or DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        learning_service=learning_service,
    )
    execution_ledger = ExecutionLedger()
    lifecycle_ledger = PositionLifecycleLedger()
    return AutoTradingService(
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
        ),
    )


class ExternalContextProviderStub:
    def snapshot(self, *, market: str, trade_coin: str) -> dict[str, object]:
        return {
            "market": market,
            "trade_coin": trade_coin,
            "onchain": {"state": "bullish"},
            "etf": {"state": "inflow"},
            "learning_weight": 1.1,
        }


def test_auto_trading_service_records_waiting_until_history_is_ready(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 801.0], min_history=4)

    result = service.tick()

    assert result["status"] == "waiting"
    assert result["reason"] == "MARKET_HISTORY_WARMING_UP"
    assert result["trading_profile"] == "scalping"


def test_auto_trading_service_records_external_context_in_learning_cycle(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0], min_history=4)
    service._external_context_provider = ExternalContextProviderStub()

    result = service.tick()
    latest = service._learning_service.recent_events()[-1]

    assert result["external_context"]["onchain"]["state"] == "bullish"
    assert latest.payload["external_context"]["etf"]["state"] == "inflow"


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


def test_auto_trading_service_can_scale_in_after_pullback_with_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0, 818.0, 823.0], min_history=4)

    for _ in range(4):
        first_entry = service.tick()
    first_portfolio = service._portfolio_state()
    first_position = service._position_store.get()

    pullback = service.tick()
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


def test_auto_trading_service_allows_medium_scalping_entries(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [2048.0, 2060.0, 2080.0, 2100.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["signal_level"] == "medium"


def test_auto_trading_service_relaxes_fee_edge_after_repeated_demo_no_trade(tmp_path: Path) -> None:
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
    )

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["signal_level"] == "weak"
    assert result["sizing_allowed"] is True
    assert result["no_trade_relaxed"] is True


def test_auto_trading_service_does_not_run_live_without_explicit_live_flag(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0], min_history=2)
    service._trading_mode = "live"
    service._config = AutoTradingConfig(
        enabled=True,
        live_enabled=False,
        interval_sec=1,
        min_history=2,
    )

    assert service.should_run() is False
