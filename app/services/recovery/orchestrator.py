from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.services.learning.service import LearningEvent
from app.services.portfolio.sync import PortfolioState, PortfolioSyncService
from app.services.recovery.hard_stop import RestartCounter


class RestartStore(Protocol):
    def record(self, event: dict[str, object]) -> None: ...


class OpenOrderReconciler(Protocol):
    def reconcile(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class BootState:
    safe_mode: bool
    hard_stop: bool
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


class FileRestartStateStore:
    """Persist restart and recovery state to a small JSON document."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: dict[str, object]) -> None:
        payload = {
            **event,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        self._path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def record_boot_state(self, event: dict[str, object]) -> None:
        self.record(event)

    def load_latest(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))


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
        restart_counter: RestartCounter | None = None,
        learning_service=None,
    ) -> None:
        self._app_name = app_name
        self._trading_mode = trading_mode
        self._portfolio_sync_service = portfolio_sync_service
        self._open_order_reconciler = open_order_reconciler
        self._restart_store = restart_store
        self._restart_counter = restart_counter
        self._learning_service = learning_service

    def boot(self) -> BootState:
        restart_event = {
            "event_name": "restart_detected",
            "app_name": self._app_name,
            "trading_mode": self._trading_mode,
        }
        self._restart_store.record(restart_event)
        self._record_learning_event("restart_detected", restart_event)
        if self._restart_counter is not None:
            hard_stop = self._restart_counter.record_restart()
            if hard_stop.hard_stop:
                self._record_learning_event(
                    "hard_stop_triggered",
                    {
                        "restart_count": hard_stop.restart_count,
                        "blocked_reason": hard_stop.blocked_reason,
                    },
                )
                return BootState(
                    safe_mode=True,
                    hard_stop=True,
                    trading_ready=False,
                    failure_stage="hard_stop",
                    portfolio_state=None,
                    reconcile_result={
                        "restart_count": hard_stop.restart_count,
                        "blocked_reason": hard_stop.blocked_reason,
                    },
                )

        try:
            portfolio_state = self._portfolio_sync_service.sync()
        except Exception:
            return BootState(
                safe_mode=True,
                hard_stop=False,
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
                hard_stop=False,
                trading_ready=False,
                failure_stage="open_order_reconcile",
                portfolio_state=portfolio_state,
                reconcile_result=None,
            )

        boot_state = BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=portfolio_state,
            reconcile_result=reconcile_result,
        )
        record_boot_state = getattr(self._restart_store, "record_boot_state", None)
        if record_boot_state is not None:
            record_boot_state(
                {
                    "event_name": "recovery_completed",
                    "app_name": self._app_name,
                    "trading_mode": self._trading_mode,
                    "safe_mode": boot_state.safe_mode,
                    "hard_stop": boot_state.hard_stop,
                    "trading_ready": boot_state.trading_ready,
                    "failure_stage": boot_state.failure_stage,
                    "reconcile_result": reconcile_result,
                },
            )
        self._record_learning_event(
            "recovery_completed",
            {
                "safe_mode": boot_state.safe_mode,
                "trading_ready": boot_state.trading_ready,
                "failure_stage": boot_state.failure_stage,
                "open_order_count": reconcile_result.get("open_order_count"),
            },
        )
        return boot_state

    def _record_learning_event(self, event_name: str, payload: dict[str, object]) -> None:
        if self._learning_service is None:
            return
        self._learning_service.record(
            LearningEvent(
                event_name=event_name,
                market="KRW-XRP",
                mode=self._trading_mode,
                payload=payload,
            ),
        )
