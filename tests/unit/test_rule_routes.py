from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.rules import build_rules_router
from app.services.rules.review import RuleReviewConfig, RuleReviewService


def test_rule_review_api_contract(tmp_path) -> None:
    service = RuleReviewService(
        market="KRW-XRP",
        trading_mode="demo",
        learning_log_dir=tmp_path,
        config=RuleReviewConfig(
            enabled=True,
            window_days=14,
            min_trades=100,
            min_stoplosses=20,
            max_params_per_run=3,
            apply_target="demo",
            require_manual_approval=True,
        ),
    )
    app = FastAPI()
    app.include_router(build_rules_router(rule_review_service=service))
    client = TestClient(app)

    review_response = client.post("/api/v1/rules/review")
    assert review_response.status_code == 200
    review = review_response.json()["review"]
    assert review["analysis_window_days"] == 14
    assert review["approval_required"] is True

    proposal_response = client.post("/api/v1/rules/proposals", json={"review_id": review["id"]})
    assert proposal_response.status_code == 200
    proposal = proposal_response.json()["proposal"]
    assert proposal["apply_target"] == "demo"

    detail_response = client.get(f"/api/v1/rules/proposals/{proposal['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["proposal"]["id"] == proposal["id"]

    demo_response = client.post(f"/api/v1/rules/proposals/{proposal['id']}/apply-demo")
    assert demo_response.status_code == 200
    assert demo_response.json()["proposal"]["demo_applied"] is False

    live_response = client.post(f"/api/v1/rules/proposals/{proposal['id']}/approve-live", json={"approved_by": ""})
    assert live_response.status_code == 200
    assert live_response.json()["proposal"]["live_approved"] is False
