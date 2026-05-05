from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.rules import build_rules_router
from app.services.rules.review import RuleReviewConfig, RuleReviewService


def test_rule_review_api_contract(tmp_path) -> None:
    service = RuleReviewService(
        market="KRW-XRP",
        trade_coin="XRP",
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
    assert review["trade_coin"] == "XRP"
    assert review["learning_log_dir"] == str(tmp_path)

    proposal_response = client.post("/api/v1/rules/proposals", json={"review_id": review["id"]})
    assert proposal_response.status_code == 200
    proposal = proposal_response.json()["proposal"]
    assert proposal["apply_target"] == "demo"
    assert proposal["trade_coin"] == "XRP"

    list_response = client.get("/api/v1/rules/proposals")
    assert list_response.status_code == 200
    assert list_response.json()["trade_coin"] == "XRP"
    assert list_response.json()["learning_log_dir"] == str(tmp_path)
    assert list_response.json()["latest_proposal"]["id"] == proposal["id"]
    assert list_response.json()["proposals"][0]["id"] == proposal["id"]

    history_response = client.get("/api/v1/rules/history")
    assert history_response.status_code == 200
    assert history_response.json()["count"] == 1
    assert history_response.json()["history"][0]["proposal_id"] == proposal["id"]

    commit_response = client.post(
        f"/api/v1/rules/proposals/{proposal['id']}/commit-hash",
        json={"commit_hash": "abc1234"},
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["proposal"]["commit_hash"] == "abc1234"

    linked_history_response = client.get("/api/v1/rules/history")
    assert linked_history_response.status_code == 200
    assert linked_history_response.json()["history"][0]["event_type"] == "commit_linked"
    assert linked_history_response.json()["history"][0]["commit_hash"] == "abc1234"

    correction_response = client.post(
        f"/api/v1/rules/proposals/{proposal['id']}/history-corrections",
        json={
            "reason": "운영 메모 보정",
            "corrected_fields": {"operator_note": "커밋 연결 확인"},
            "corrected_by": "operator",
        },
    )
    assert correction_response.status_code == 200
    assert correction_response.json()["correction"]["reason"] == "운영 메모 보정"

    corrected_history_response = client.get("/api/v1/rules/history")
    assert corrected_history_response.status_code == 200
    assert corrected_history_response.json()["history"][0]["event_type"] == "correction"
    assert corrected_history_response.json()["history"][0]["correction_detail"]["corrected_by"] == "operator"

    detail_response = client.get(f"/api/v1/rules/proposals/{proposal['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["proposal"]["id"] == proposal["id"]
    assert detail_response.json()["proposal"]["commit_hash"] == "abc1234"

    demo_response = client.post(f"/api/v1/rules/proposals/{proposal['id']}/apply-demo")
    assert demo_response.status_code == 200
    assert demo_response.json()["proposal"]["demo_applied"] is False

    replay_response = client.post(
        f"/api/v1/rules/proposals/{proposal['id']}/replay",
        json={"fixture_path": "fixtures/replay_ticks.json"},
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["proposal"]["replay_result"]["status"] == "passed"

    live_response = client.post(f"/api/v1/rules/proposals/{proposal['id']}/approve-live", json={"approved_by": ""})
    assert live_response.status_code == 200
    assert live_response.json()["proposal"]["live_approved"] is False
