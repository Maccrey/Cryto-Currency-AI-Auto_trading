from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.learning import build_learning_router
from app.services.learning.service import LearningEvent, LearningService


def test_learning_model_readiness_endpoint_returns_readiness_payload(tmp_path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record(
        LearningEvent(
            event_name="signal_generated",
            market="KRW-XRP",
            mode="demo",
            payload={"level": "strong"},
        ),
    )
    app = FastAPI()
    app.include_router(
        build_learning_router(
            market="KRW-XRP",
            learning_service=learning_service,
            learning_log_dir=tmp_path,
        ),
    )

    response = TestClient(app).get("/learning/model-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["market"] == "KRW-XRP"
    assert payload["readiness"]["status"] == "not_ready"
    assert "tensorflow" in payload["readiness"]["planned_packages"]
