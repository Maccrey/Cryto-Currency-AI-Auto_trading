from pathlib import Path

from app.services.dashboard.recovery import DashboardRecoveryService
from app.services.dashboard.recovery_facade import DashboardRecoveryFacade
from app.services.learning.service import LearningEvent, LearningService
from app.services.recovery.orchestrator import BootState


def test_dashboard_recovery_facade_returns_boot_state_and_recent_events(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="restart_detected",
                market="KRW-XRP",
                mode="demo",
                payload={"app_name": "test-app"},
                recorded_at="2026-04-20T09:00:00+09:00",
            ),
            LearningEvent(
                event_name="recovery_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"trading_ready": True},
                recorded_at="2026-04-20T09:00:05+09:00",
            ),
        ],
    )
    facade = DashboardRecoveryFacade(
        boot_state=BootState(
            safe_mode=False,
            hard_stop=False,
            trading_ready=True,
            failure_stage=None,
            portfolio_state=None,
            reconcile_result=None,
        ),
        learning_service=learning_service,
        dashboard_recovery_service=DashboardRecoveryService(),
    )

    response = facade.build_response(limit=5)

    assert response["status"] == "ok"
    assert response["recovery"]["safe_mode"] is False
    assert response["recovery"]["hard_stop"] is False
    assert response["recovery"]["trading_ready"] is True
    assert response["recovery"]["failure_stage"] is None
    assert response["recovery"]["restart_count"] is None
    assert response["recovery"]["blocked_reason"] is None
    assert response["recovery"]["last_restart_detected_at"] == "2026-04-20T09:00:00+09:00"
    assert response["recovery"]["last_recovery_completed_at"] == "2026-04-20T09:00:05+09:00"
    assert response["recovery"]["hard_stop_triggered_at"] is None
    assert [event["event_name"] for event in response["recovery"]["recent_events"]] == [
        "restart_detected",
        "recovery_completed",
    ]
    assert response["recovery"]["recent_hard_stop_events"] == []
    assert response["recovery"]["recent_hard_stop_timeline"] == []


def test_dashboard_recovery_facade_includes_hard_stop_history(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="restart_detected",
                market="KRW-XRP",
                mode="live",
                payload={"app_name": "test-app"},
                recorded_at="2026-04-20T09:10:00+09:00",
            ),
            LearningEvent(
                event_name="hard_stop_triggered",
                market="KRW-XRP",
                mode="live",
                payload={
                    "restart_count": 3,
                    "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
                },
                recorded_at="2026-04-20T09:10:01+09:00",
            ),
        ],
    )
    facade = DashboardRecoveryFacade(
        boot_state=BootState(
            safe_mode=True,
            hard_stop=True,
            trading_ready=False,
            failure_stage="hard_stop",
            portfolio_state=None,
            reconcile_result={
                "restart_count": 3,
                "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
            },
        ),
        learning_service=learning_service,
        dashboard_recovery_service=DashboardRecoveryService(),
    )

    response = facade.build_response(limit=5)

    assert response["recovery"]["hard_stop"] is True
    assert response["recovery"]["failure_stage"] == "hard_stop"
    assert response["recovery"]["restart_count"] == 3
    assert response["recovery"]["blocked_reason"] == "RESTART_THRESHOLD_EXCEEDED"
    assert response["recovery"]["hard_stop_triggered_at"] == "2026-04-20T09:10:01+09:00"
    assert [event["event_name"] for event in response["recovery"]["recent_hard_stop_events"]] == [
        "hard_stop_triggered",
    ]
    assert response["recovery"]["recent_hard_stop_timeline"] == [
        {
            "triggered_at": "2026-04-20T09:10:01+09:00",
            "restart_count": 3,
            "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
        },
    ]
