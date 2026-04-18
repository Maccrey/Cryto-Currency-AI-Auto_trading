from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.portfolio.sync import PortfolioState, PortfolioSyncService


class RestartStore(Protocol):
    def record(self, event: dict[str, object]) -> None: ...


class OpenOrderReconciler(Protocol):
    def reconcile(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class BootState:
    safe_mode: bool
    trading_ready: bool
    failure_stage: str | None
    portfolio_state: PortfolioState | None
    reconcile_result: dict[str, object] | None


class InMemoryRestartStore:
    """Temporary restart store until structured event persistence is added."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def record(self, event: dict[str, object]) -> None:
        self.events.append(event)


class NullOpenOrderReconciler:
    """Default reconciler that marks reconciliation as pending implementation."""

    def reconcile(self) -> dict[str, object]:
        return {"open_order_count": 0, "status": "not_implemented"}


class RecoveryOrchestrator:
    """Boot sequence controller for restart logging, sync, and reconcile stages."""

    def __init__(
        self,
        *,
        app_name: str,
        trading_mode: str,
        portfolio_sync_service: PortfolioSyncService,
        open_order_reconciler: OpenOrderReconciler,
        restart_store: RestartStore,
    ) -> None:
        self._app_name = app_name
        self._trading_mode = trading_mode
        self._portfolio_sync_service = portfolio_sync_service
        self._open_order_reconciler = open_order_reconciler
        self._restart_store = restart_store

    def boot(self) -> BootState:
        self._restart_store.record(
            {
                "event_name": "restart_detected",
                "app_name": self._app_name,
                "trading_mode": self._trading_mode,
            },
        )

        try:
            portfolio_state = self._portfolio_sync_service.sync()
        except Exception:
            return BootState(
                safe_mode=True,
                trading_ready=False,
                failure_stage="portfolio_sync",
                portfolio_state=None,
                reconcile_result=None,
            )

        try:
            reconcile_result = self._open_order_reconciler.reconcile()
        except Exception:
            return BootState(
                safe_mode=True,
                trading_ready=False,
                failure_stage="open_order_reconcile",
                portfolio_state=portfolio_state,
                reconcile_result=None,
            )

        return BootState(
            safe_mode=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=portfolio_state,
            reconcile_result=reconcile_result,
        )

