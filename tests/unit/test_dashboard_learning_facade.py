from pathlib import Path

from app.services.dashboard.learning import DashboardLearningService
from app.services.dashboard.learning_facade import DashboardLearningFacade
from app.services.learning.service import LearningEvent, LearningService


def test_dashboard_learning_facade_returns_summary_and_recent_events(tmp_path: Path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"level": "strong"},
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"side": "buy"},
            ),
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={"quantity": 100.0},
            ),
        ],
    )
    facade = DashboardLearningFacade(
        learning_service=learning_service,
        dashboard_learning_service=DashboardLearningService(),
    )

    response = facade.build_response(limit=2)

    assert response["status"] == "ok"
    assert response["learning"]["total_events"] == 2
    assert response["learning"]["last_event_name"] == "position_opened"
    assert response["learning"]["event_counts"] == {
        "fill_result": 1,
        "position_opened": 1,
    }
    assert [event["event_name"] for event in response["learning"]["recent_events"]] == [
        "fill_result",
        "position_opened",
    ]


def test_dashboard_learning_facade_returns_empty_without_events(tmp_path: Path) -> None:
    facade = DashboardLearningFacade(
        learning_service=LearningService(log_dir=tmp_path),
        dashboard_learning_service=DashboardLearningService(),
    )

    assert facade.build_response() == {
        "status": "empty",
        "learning": None,
    }
