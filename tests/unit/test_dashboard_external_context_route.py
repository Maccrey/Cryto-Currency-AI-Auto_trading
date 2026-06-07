from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.dashboard import build_dashboard_router
from app.services.recovery.orchestrator import BootState


def _client_with_provider(provider):
    app = FastAPI()
    app.include_router(
        build_dashboard_router(
            boot_state=BootState(
                safe_mode=False,
                hard_stop=False,
                trading_ready=True,
                failure_stage=None,
                portfolio_state=None,
                reconcile_result=None,
            ),
            trading_mode="demo",
            trading_profile="scalping",
            trading_profile_label="단타",
            learning_enabled=True,
            dashboard_summary_facade=object(),
            dashboard_market_facade=object(),
            dashboard_executions_facade=object(),
            dashboard_positions_facade=object(),
            dashboard_learning_facade=object(),
            dashboard_recovery_facade=object(),
            promotion_dashboard_facade=object(),
            external_context_provider=provider,
        ),
    )
    return TestClient(app)


def test_dashboard_external_context_calls_provider_with_force_flag() -> None:
    calls = []

    def provider(*, force=False):
        calls.append(force)
        return {
            "trade_coin": "XRP",
            "recorded_at": "2026-06-07T12:00:00+09:00",
            "learning_weight": 1.2,
            "market_data": {"usd_price": 0.5, "usd_change_pct_24h": 0.01},
            "onchain": {"state": "bullish", "source": "web", "data_status": "provider"},
            "etf": {"state": "inflow", "source": "web", "data_status": "provider", "flow_usd": 1250000},
        }

    response = _client_with_provider(provider).get("/dashboard/external-context?force=true")

    assert response.status_code == 200
    payload = response.json()
    assert calls == [True]
    assert payload["status"] == "ok"
    assert payload["context"]["market_data"]["usd_price"] == 0.5
    assert payload["context"]["onchain"]["state"] == "bullish"
    assert payload["context"]["etf"]["state"] == "inflow"


def test_dashboard_external_context_supports_legacy_provider_without_force_argument() -> None:
    response = _client_with_provider(lambda: {"onchain": {"state": "neutral"}}).get("/dashboard/external-context")

    assert response.status_code == 200
    assert response.json()["context"]["onchain"]["state"] == "neutral"
