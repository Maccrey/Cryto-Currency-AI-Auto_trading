from __future__ import annotations

import json
import time
from collections.abc import Callable
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


@dataclass(frozen=True)
class RecoveryRetryPolicy:
    max_attempts: int = 3
    retry_delay_sec: float = 1.0


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
        retry_policy: RecoveryRetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
        learning_service=None,
        market: str = "KRW-XRP",
    ) -> None:
        self._app_name = app_name
        self._trading_mode = trading_mode
        self._portfolio_sync_service = portfolio_sync_service
        self._open_order_reconciler = open_order_reconciler
        self._restart_store = restart_store
        self._restart_counter = restart_counter
        self._retry_policy = retry_policy or RecoveryRetryPolicy()
        self._sleep = sleep or time.sleep
        self._learning_service = learning_service
        self._market = market

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

        portfolio_state = self._recover_stage(
            stage="portfolio_sync",
            operation=self._portfolio_sync_service.sync,
        )
        if portfolio_state is None:
            return BootState(
                safe_mode=True,
                hard_stop=False,
                trading_ready=False,
                failure_stage="portfolio_sync",
                portfolio_state=None,
                reconcile_result=None,
            )

        reconcile_result = self._recover_stage(
            stage="open_order_reconcile",
            operation=self._open_order_reconciler.reconcile,
        )
        if reconcile_result is None:
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

    def _recover_stage(self, *, stage: str, operation):
        max_attempts = max(self._retry_policy.max_attempts, 1)
        for attempt in range(1, max_attempts + 1):
            try:
                result = operation()
            except Exception as exc:
                self._record_recovery_attempt(
                    stage=stage,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    status="failed",
                    error=str(exc),
                )
                if attempt < max_attempts and self._retry_policy.retry_delay_sec > 0:
                    self._sleep(self._retry_policy.retry_delay_sec)
                continue

            if attempt > 1:
                self._record_recovery_attempt(
                    stage=stage,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    status="recovered",
                    error=None,
                )
            return result
        return None

    def _record_recovery_attempt(
        self,
        *,
        stage: str,
        attempt: int,
        max_attempts: int,
        status: str,
        error: str | None,
    ) -> None:
        event = {
            "event_name": "recovery_attempt",
            "app_name": self._app_name,
            "trading_mode": self._trading_mode,
            "stage": stage,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "status": status,
            "error": error,
        }
        self._restart_store.record(event)
        self._record_learning_event("recovery_attempt", event)

    def _record_learning_event(self, event_name: str, payload: dict[str, object]) -> None:
        if self._learning_service is None:
            return
        self._learning_service.record(
            LearningEvent(
                event_name=event_name,
                market=self._market,
                mode=self._trading_mode,
                payload=payload,
            ),
        )
