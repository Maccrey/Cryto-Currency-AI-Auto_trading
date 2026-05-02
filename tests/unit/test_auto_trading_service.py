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
from app.services.trading.auto import AutoTradingConfig, AutoTradingService
from app.services.trading.decision import TradeDecisionService
from app.services.trading.execution import TradeExecutionService
from app.services.trading.post_fill import PostFillService
from app.services.learning.service import LearningService


class ForbiddenLiveOrderGateway:
    def place_order(self, **kwargs):
        raise AssertionError("live gateway should not be called in auto demo trading")


class SequenceTickerProvider:
    def __init__(self, prices: list[float]) -> None:
        self._prices = list(prices)

    def get_current_snapshot(self, market: str) -> UpbitTickerSnapshot:
        price = self._prices.pop(0)
        return UpbitTickerSnapshot(
            trade_price=price,
            acc_trade_price_24h=price * 1000,
        )


def _build_service(tmp_path: Path, prices: list[float], *, min_history: int = 4) -> AutoTradingService:
    learning_service = LearningService(log_dir=tmp_path)
    position_store = CurrentPositionStore()
    executor = DemoExecutor(
        live_order_gateway=ForbiddenLiveOrderGateway(),
        learning_service=learning_service,
    )
    execution_ledger = ExecutionLedger()
    lifecycle_ledger = PositionLifecycleLedger()
    return AutoTradingService(
        market="KRW-XRP",
        trading_mode="demo",
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
                trading_mode="demo",
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
                    "weak": 0.008,
                    "medium": 0.012,
                    "strong": 0.018,
                    "very_strong": 0.022,
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
            trading_mode="demo",
            learning_service=learning_service,
            execution_ledger=execution_ledger,
            position_lifecycle_ledger=lifecycle_ledger,
        ),
        learning_service=learning_service,
        config=AutoTradingConfig(
            enabled=True,
            live_enabled=False,
            interval_sec=1,
            min_history=min_history,
        ),
    )


def test_auto_trading_service_records_waiting_until_history_is_ready(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 801.0], min_history=4)

    result = service.tick()

    assert result["status"] == "waiting"
    assert result["reason"] == "MARKET_HISTORY_WARMING_UP"
    assert result["trading_profile"] == "scalping"


def test_auto_trading_service_executes_demo_trade_after_signal(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [800.0, 806.0, 813.0, 824.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    event_names = [event.event_name for event in service._learning_service.recent_events()]
    assert "auto_trade_cycle" in event_names
    assert "fill_result" in event_names
    assert "position_opened" in event_names


def test_auto_trading_service_allows_medium_scalping_entries(tmp_path: Path) -> None:
    service = _build_service(tmp_path, [2048.0, 2060.0, 2080.0, 2100.0], min_history=4)

    for _ in range(4):
        result = service.tick()

    assert result["status"] == "filled"
    assert result["signal_level"] == "medium"


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
