from copy import deepcopy

from app.services.dashboard.facade import DashboardSummaryFacade
from app.services.dashboard.promotion import PromotionDashboardService
from app.services.dashboard.summary import DashboardSummaryService
from app.services.execution.demo import FillResult
from app.services.execution.ledger import ExecutionLedger
from app.services.learning.service import LearningEvent, LearningService
from app.services.market.store import MarketPriceStore
from app.services.position.ledger import PositionLifecycleLedger
from app.services.position.store import CurrentPositionStore
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult
from app.services.promotion.state import PromotionStateService
from app.services.promotion.dashboard import PromotionDashboardFacade
from app.services.portfolio.sync import PortfolioState
from app.services.recovery.orchestrator import BootState
from app.services.risk.stop_loss import PositionSnapshot


def _with_section_card_objects(payload: dict[str, object]) -> dict[str, object]:
    normalized = deepcopy(payload)
    normalized["summary_object"] = {
        "coin_balance": normalized.get("coin_balance"),
        "cash_balance": normalized.get("cash_balance"),
        "realized_pnl": normalized.get("realized_pnl"),
        "unrealized_pnl": normalized.get("unrealized_pnl"),
        "buy_count": normalized.get("buy_count"),
        "sell_count": normalized.get("sell_count"),
        "stop_loss_count": normalized.get("stop_loss_count"),
        "recent_stop_loss_reason": normalized.get("recent_stop_loss_reason"),
        "trading_mode": normalized.get("trading_mode"),
        "learning_enabled": normalized.get("learning_enabled"),
        "promotion_ready": normalized.get("promotion_ready"),
        "safe_mode": normalized.get("safe_mode"),
        "hard_stop": normalized.get("hard_stop"),
        "trading_ready": normalized.get("trading_ready"),
    }
    for section in normalized["sections"]:
        section["card_object"] = {
            "state": section["section_objects"]["state"],
            "action": section["section_objects"]["action"],
            "freshness": section["section_objects"]["freshness"],
            "route": section["section_objects"]["route"],
            "metrics": section["metrics"],
            "metric_items": section["metric_items"],
            "freshness_metric_items": section["freshness_metric_items"],
        }
    normalized["cards"] = [
        {
            "key": section["key"],
            "name": section["name"],
            "card": section["card_object"],
            "state": section["state_object"],
            "action": section["action_state"],
            "freshness": section["freshness_state_object"],
            "route": section["action_route"],
        }
        for section in normalized["sections"]
    ]
    normalized["card_map"] = {card["key"]: card for card in normalized["cards"]}
    normalized["card_order"] = [card["key"] for card in normalized["cards"]]
    severity_counts = {"info": 0, "warning": 0, "critical": 0}
    actionable_count = 0
    stale_count = 0
    for card in normalized["cards"]:
        severity = card["state"]["severity"]
        if severity in severity_counts:
            severity_counts[severity] += 1
        if card["action"]["actionable"]:
            actionable_count += 1
        if card["freshness"]["stale"]:
            stale_count += 1
    normalized["card_meta"] = {
        "count": len(normalized["cards"]),
        "keys": [card["key"] for card in normalized["cards"]],
        "severity_counts": severity_counts,
        "actionable_count": actionable_count,
        "stale_count": stale_count,
    }
    normalized["cards_object"] = {
        "cards": normalized["cards"],
        "card_map": normalized["card_map"],
        "card_order": normalized["card_order"],
        "card_meta": normalized["card_meta"],
    }
    normalized["dashboard_meta"] = {
        "section_count": len(normalized["sections"]),
        "card_count": len(normalized["cards"]),
        "section_keys": [section["key"] for section in normalized["sections"]],
        "card_keys": [card["key"] for card in normalized["cards"]],
        "severity_counts": {
            "info": sum(1 for section in normalized["sections"] if section["severity"] == "info"),
            "warning": sum(1 for section in normalized["sections"] if section["severity"] == "warning"),
            "critical": sum(1 for section in normalized["sections"] if section["severity"] == "critical"),
        },
        "actionable_section_count": sum(
            1 for section in normalized["sections"] if section["actionable"]
        ),
        "actionable_section_keys": [
            section["key"] for section in normalized["sections"] if section["actionable"]
        ],
        "freshness_counts": {
            "fresh": sum(1 for section in normalized["sections"] if section["freshness_state"] == "fresh"),
            "stale": sum(1 for section in normalized["sections"] if section["freshness_state"] == "stale"),
            "missing": sum(1 for section in normalized["sections"] if section["freshness_state"] == "missing"),
        },
        "stale_section_count": sum(
            1 for section in normalized["sections"] if section["stale"]
        ),
        "stale_section_keys": [
            section["key"] for section in normalized["sections"] if section["stale"]
        ],
        "meta_object": {
            "counts": {
                "section_count": len(normalized["sections"]),
                "card_count": len(normalized["cards"]),
                "actionable_section_count": sum(
                    1 for section in normalized["sections"] if section["actionable"]
                ),
                "stale_section_count": sum(
                    1 for section in normalized["sections"] if section["stale"]
                ),
            },
            "keys": {
                "section_keys": [section["key"] for section in normalized["sections"]],
                "card_keys": [card["key"] for card in normalized["cards"]],
                "actionable_section_keys": [
                    section["key"] for section in normalized["sections"] if section["actionable"]
                ],
                "stale_section_keys": [
                    section["key"] for section in normalized["sections"] if section["stale"]
                ],
            },
            "severity_counts": {
                "info": sum(1 for section in normalized["sections"] if section["severity"] == "info"),
                "warning": sum(1 for section in normalized["sections"] if section["severity"] == "warning"),
                "critical": sum(1 for section in normalized["sections"] if section["severity"] == "critical"),
            },
            "freshness_counts": {
                "fresh": sum(1 for section in normalized["sections"] if section["freshness_state"] == "fresh"),
                "stale": sum(1 for section in normalized["sections"] if section["freshness_state"] == "stale"),
                "missing": sum(1 for section in normalized["sections"] if section["freshness_state"] == "missing"),
            },
        },
    }
    normalized["dashboard_order"] = ["summary", "cards", "meta"]
    normalized["dashboard_labels"] = {
        "summary": "Summary",
        "cards": "Cards",
        "meta": "Meta",
    }
    normalized["dashboard_panels"] = [
        {
            "key": "summary",
            "label": normalized["dashboard_labels"]["summary"],
            "data": normalized["summary_object"],
        },
        {
            "key": "cards",
            "label": normalized["dashboard_labels"]["cards"],
            "data": normalized["cards_object"],
        },
        {
            "key": "meta",
            "label": normalized["dashboard_labels"]["meta"],
            "data": normalized["dashboard_meta"],
        },
    ]
    normalized["dashboard_panel_map"] = {
        panel["key"]: panel
        for panel in normalized["dashboard_panels"]
    }
    normalized["dashboard_panel_meta"] = {
        "count": len(normalized["dashboard_panels"]),
        "keys": [panel["key"] for panel in normalized["dashboard_panels"]],
    }
    normalized["dashboard_object"] = {
        "summary": normalized["summary_object"],
        "cards": normalized["cards_object"],
        "meta": normalized["dashboard_meta"],
        "order": normalized["dashboard_order"],
        "labels": normalized["dashboard_labels"],
        "panels": normalized["dashboard_panels"],
        "panel_map": normalized["dashboard_panel_map"],
        "panel_meta": normalized["dashboard_panel_meta"],
    }
    return normalized


def test_dashboard_summary_facade_builds_payload_with_promotion_state() -> None:
    promotion_state_service = PromotionStateService()
    promotion_state_service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T18:00:00+09:00",
        result=PromotionRunResult(
            evaluation=PromotionEvaluation(
                status="READY_FOR_REVIEW",
                approved=False,
                rejection_reasons=[],
            ),
            approval_result=PromotionApprovalResult(
                live_enabled=True,
                safe_mode_entry=True,
                reason_code=None,
            ),
        ),
    )
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=promotion_state_service,
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        timestamp_provider=lambda: "2026-04-19T20:00:00+09:00",
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=180.5,
            avg_buy_price=815.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload == _with_section_card_objects({
        "coin_balance": 180.5,
        "cash_balance": 250000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "stop_loss_count": 0,
        "recent_stop_loss_reason": None,
        "trading_mode": "demo",
        "learning_enabled": True,
        "last_learning_event": None,
        "learning_signal_count": 0,
        "learning_fill_count": 0,
        "last_signal_recorded_at": None,
        "last_fill_recorded_at": None,
        "last_position_event": None,
        "last_promotion_reviewed_at": "2026-04-19T18:00:00+09:00",
        "last_restart_detected_at": None,
        "last_recovery_completed_at": None,
        "sections": [
            {
                "key": "trading",
                "name": "Trading",
                "state_label": "NORMAL",
                "severity": "info",
                "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.",
                "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요.",
                "state_object": {"state_label": "NORMAL", "severity": "info", "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.", "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요."},
                "recommended_action_label": "MONITOR_TRADING_SECTION",
                "action_group": "monitor",
                "action_priority": "low",
                "actionable": False,
                "action_state": {"recommended_action_label": "MONITOR_TRADING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "action_url_key": "dashboard.executions",
                "action_tab_key": "timeline",
                "action_target": "execution_timeline",
                "action_params": {"section": "trading"},
                "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
                "section_objects": {
                    "state": {"state_label": "NORMAL", "severity": "info", "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.", "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요."},
                    "action": {"recommended_action_label": "MONITOR_TRADING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                    "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                    "route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
                },
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 300,
                "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}}, "value": 300},
                ],
                "metrics": {
                    "buy_count": 0,
                    "sell_count": 0,
                    "stop_loss_count": 0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "recent_stop_loss_reason": None,
                },
                "metric_items": [
                    {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "buy_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "buy_count"}}, "value": 0},
                    {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "sell_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "sell_count"}}, "value": 0},
                    {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Stop Loss Count 0', "recommended_action": '손절 카운트를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "stop_loss_count", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "stop_loss_count", "highlight_reason": True}}, "value": 0},
                    {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "realized_pnl"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "realized_pnl"}}, "value": 0.0},
                    {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "action_target": "current_position", "action_params": {"focus_metric": "unrealized_pnl"}, "action_route": {"url_key": "dashboard.positions.current", "tab_key": "current", "target": "current_position", "params": {"focus_metric": "unrealized_pnl"}}, "value": 0.0},
                    {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Recent Stop Loss Reason 기록 없음', "recommended_action": '손절 사유 발생 여부만 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS_REASON', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}}, "value": None},
                ],
            },
            {
                "key": "learning",
                "name": "Learning",
                "state_label": "ACTIVE",
                "severity": "info",
                "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
                "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
                "state_object": {"state_label": "ACTIVE", "severity": "info", "state_message": "학습 이벤트 기록이 활성화되어 있습니다.", "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요."},
                "recommended_action_label": "MONITOR_LEARNING_SECTION",
                "action_group": "monitor",
                "action_priority": "low",
                "actionable": False,
                "action_state": {"recommended_action_label": "MONITOR_LEARNING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "action_url_key": "dashboard.learning",
                "action_tab_key": "recent-events",
                "action_target": "learning_recent_events",
                "action_params": {"section": "learning"},
                "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"section": "learning"}},
                "section_objects": {
                    "state": {"state_label": "ACTIVE", "severity": "info", "state_message": "학습 이벤트 기록이 활성화되어 있습니다.", "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요."},
                    "action": {"recommended_action_label": "MONITOR_LEARNING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                    "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                    "route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"section": "learning"}},
                },
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 300,
                "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}}, "value": 300},
                ],
                "metrics": {
                    "last_learning_event": None,
                    "learning_signal_count": 0,
                    "learning_fill_count": 0,
                    "last_signal_recorded_at": None,
                    "last_fill_recorded_at": None,
                },
                "metric_items": [
                    {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_learning_event"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_learning_event"}}, "value": None},
                    {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_signal_count", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_signal_count", "event_type": "signal"}}, "value": 0},
                    {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_fill_count", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_fill_count", "event_type": "fill"}}, "value": 0},
                    {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}}, "value": None},
                    {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}}, "value": None},
                ],
            },
            {
                "key": "recovery",
                "name": "Recovery",
                "state_label": "OK",
                "severity": "info",
                "state_message": "복구 상태가 정상입니다.",
                "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
                "state_object": {"state_label": "OK", "severity": "info", "state_message": "복구 상태가 정상입니다.", "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요."},
                "recommended_action_label": "MONITOR_RECOVERY_SECTION",
                "action_group": "monitor",
                "action_priority": "low",
                "actionable": False,
                "action_state": {"recommended_action_label": "MONITOR_RECOVERY_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "action_url_key": "dashboard.recovery",
                "action_tab_key": "status",
                "action_target": "recovery_status",
                "action_params": {"section": "recovery"},
                "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"section": "recovery"}},
                "section_objects": {
                    "state": {"state_label": "OK", "severity": "info", "state_message": "복구 상태가 정상입니다.", "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요."},
                    "action": {"recommended_action_label": "MONITOR_RECOVERY_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                    "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 600},
                    "route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"section": "recovery"}},
                },
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 600,
                "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 600},
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}}, "value": 600},
                ],
                "metrics": {
                    "safe_mode": False,
                    "hard_stop": False,
                    "trading_ready": True,
                    "failure_stage": None,
                    "last_restart_detected_at": None,
                    "last_recovery_completed_at": None,
                },
                "metric_items": [
                    {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "safe_mode"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "safe_mode"}}, "value": False},
                    {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "hard_stop"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "hard_stop"}}, "value": False},
                    {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "trading_ready"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "trading_ready"}}, "value": True},
                    {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "failure_stage"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "failure_stage"}}, "value": None},
                    {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}}, "value": None},
                    {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}}, "value": None},
                ],
            },
            {
                "key": "promotion",
                "name": "Promotion",
                "state_label": "READY",
                "severity": "info",
                "state_message": "실거래 승격 검토 준비가 완료되었습니다.",
                "recommended_action": "승격 검토 또는 수동 승인 절차를 진행하세요.",
                "state_object": {"state_label": "READY", "severity": "info", "state_message": "실거래 승격 검토 준비가 완료되었습니다.", "recommended_action": "승격 검토 또는 수동 승인 절차를 진행하세요."},
                "recommended_action_label": "PROCEED_PROMOTION_SECTION",
                "action_group": "proceed",
                "action_priority": "high",
                "actionable": True,
                "action_state": {"recommended_action_label": "PROCEED_PROMOTION_SECTION", "action_group": "proceed", "action_priority": "high", "actionable": True},
                "action_url_key": "dashboard.promotion",
                "action_tab_key": "status",
                "action_target": "promotion_status",
                "action_params": {"section": "promotion"},
                "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"section": "promotion"}},
                "section_objects": {
                    "state": {"state_label": "READY", "severity": "info", "state_message": "실거래 승격 검토 준비가 완료되었습니다.", "recommended_action": "승격 검토 또는 수동 승인 절차를 진행하세요."},
                    "action": {"recommended_action_label": "PROCEED_PROMOTION_SECTION", "action_group": "proceed", "action_priority": "high", "actionable": True},
                    "freshness": {"updated_at": "2026-04-19T18:00:00+09:00", "stale": False, "age_sec": 7200, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 86400},
                    "route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"section": "promotion"}},
                },
                "updated_at": "2026-04-19T18:00:00+09:00",
                "stale": False,
                "age_sec": 7200,
                "freshness_state": "fresh",
                "freshness_message": "최근 데이터",
                "freshness_label": "RECENT",
                "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                "freshness_severity": "info",
                "freshness_window_sec": 86400,
                "freshness_state_object": {"updated_at": "2026-04-19T18:00:00+09:00", "stale": False, "age_sec": 7200, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 86400},
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T18:00:00+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}}, "value": "2026-04-19T18:00:00+09:00"},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 7200', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}}, "value": 7200},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}}, "value": 86400},
                ],
                "metrics": {
                    "promotion_ready": True,
                    "last_promotion_reviewed_at": "2026-04-19T18:00:00+09:00",
                },
                "metric_items": [
                    {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Promotion Ready 준비됨', "recommended_action": '승격 검토 또는 승인 절차를 진행하세요.', "recommended_action_label": 'PROCEED_PROMOTION', "action_group": 'proceed', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "promotion_ready"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "promotion_ready"}}, "value": True},
                    {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 2026-04-19T18:00:00+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "last_promotion_reviewed_at"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "last_promotion_reviewed_at"}}, "value": "2026-04-19T18:00:00+09:00"},
                ],
            },
        ],
        "section_state_label": {
            "trading": "NORMAL",
            "learning": "ACTIVE",
            "recovery": "OK",
            "promotion": "READY",
        },
        "section_severity": {
            "trading": "info",
            "learning": "info",
            "recovery": "info",
            "promotion": "info",
        },
        "section_state_message": {
            "trading": "최근 체결 기준 거래 리스크 이상이 없습니다.",
            "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recovery": "복구 상태가 정상입니다.",
            "promotion": "실거래 승격 검토 준비가 완료되었습니다.",
        },
        "section_recommended_action": {
            "trading": "현재 거래 섹션은 모니터링만 유지하세요.",
            "learning": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
            "recovery": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
            "promotion": "승격 검토 또는 수동 승인 절차를 진행하세요.",
        },
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "promotion_ready": True,
    })


def test_dashboard_summary_facade_includes_execution_ledger_stats() -> None:
    ledger = ExecutionLedger()
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="buy",
            filled_price=820.0,
            filled_quantity=100.0,
            fee=34.12,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=False,
        ),
    )
    ledger.record_fill(
        FillResult(
            market="KRW-XRP",
            side="sell",
            filled_price=805.0,
            filled_quantity=100.0,
            fee=33.5,
            status="filled",
            mode="demo",
            is_virtual=True,
            is_stop_loss=True,
        ),
        reason_code="STOP_LOSS_PRICE_HIT",
    )
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        execution_ledger=ledger,
        timestamp_provider=lambda: "2026-04-19T20:00:00+09:00",
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload["buy_count"] == 1
    assert payload["sell_count"] == 1
    assert payload["stop_loss_count"] == 1
    assert payload["recent_stop_loss_reason"] == "STOP_LOSS_PRICE_HIT"
    assert payload["realized_pnl"] < 0.0
    assert payload["last_learning_event"] is None
    assert payload["learning_signal_count"] == 0
    assert payload["learning_fill_count"] == 0
    assert payload["last_signal_recorded_at"] is None
    assert payload["last_fill_recorded_at"] is None
    assert payload["last_position_event"] is None
    assert payload["last_promotion_reviewed_at"] is None
    assert payload["last_restart_detected_at"] is None
    assert payload["last_recovery_completed_at"] is None
    sections = {section["key"]: section for section in payload["sections"]}
    assert set(sections) == {"trading", "learning", "recovery", "promotion"}
    assert sections["trading"]["action_route"] == {
        "url_key": "dashboard.executions",
        "tab_key": "timeline",
        "target": "execution_timeline",
        "params": {"section": "trading"},
    }
    assert sections["trading"]["state_label"] == "STOP_LOSS_TRIGGERED"
    assert sections["trading"]["severity"] == "critical"
    assert sections["trading"]["metrics"]["buy_count"] == 1
    assert sections["trading"]["metrics"]["sell_count"] == 1
    assert sections["trading"]["metrics"]["stop_loss_count"] == 1
    assert sections["trading"]["metrics"]["recent_stop_loss_reason"] == "STOP_LOSS_PRICE_HIT"
    assert sections["learning"]["action_route"] == {
        "url_key": "dashboard.learning",
        "tab_key": "recent-events",
        "target": "learning_recent_events",
        "params": {"section": "learning"},
    }
    assert sections["recovery"]["action_route"] == {
        "url_key": "dashboard.recovery",
        "tab_key": "status",
        "target": "recovery_status",
        "params": {"section": "recovery"},
    }
    assert sections["promotion"]["action_route"] == {
        "url_key": "dashboard.promotion",
        "tab_key": "status",
        "target": "promotion_status",
        "params": {"section": "promotion"},
    }
    assert payload["section_state_label"] == {
        "trading": "STOP_LOSS_TRIGGERED",
        "learning": "ACTIVE",
        "recovery": "OK",
        "promotion": "NOT_READY",
    }
    assert payload["section_severity"] == {
        "trading": "critical",
        "learning": "info",
        "recovery": "info",
        "promotion": "warning",
    }
    assert payload["section_state_message"] == {
        "trading": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
        "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
        "recovery": "복구 상태가 정상입니다.",
        "promotion": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
    }
    assert payload["section_recommended_action"] == {
        "trading": "최근 손절 발생 원인과 청산 흐름을 점검하세요.",
        "learning": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
        "recovery": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
        "promotion": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
    }


def test_dashboard_summary_facade_includes_unrealized_pnl_from_latest_price() -> None:
    position_store = CurrentPositionStore()
    position_store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    market_price_store = MarketPriceStore()
    market_price_store.save(market="KRW-XRP", price=845.0)
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=PromotionStateService(),
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        position_store=position_store,
        market_price_store=market_price_store,
        timestamp_provider=lambda: "2026-04-19T20:00:00+09:00",
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=100.0,
            avg_buy_price=820.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload["unrealized_pnl"] == 2500.0
    assert payload["last_learning_event"] is None
    assert payload["last_signal_recorded_at"] is None
    assert payload["last_fill_recorded_at"] is None
    assert payload["last_position_event"] is None
    assert payload["last_promotion_reviewed_at"] is None
    assert payload["last_restart_detected_at"] is None
    assert payload["last_recovery_completed_at"] is None
    assert payload["sections"] == _with_section_card_objects({"sections": [
        {
            "key": "trading",
            "name": "Trading",
            "state_label": "NORMAL",
            "severity": "info",
            "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.",
            "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요.",
            "state_object": {"state_label": "NORMAL", "severity": "info", "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.", "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요."},
            "recommended_action_label": "MONITOR_TRADING_SECTION",
            "action_group": "monitor",
            "action_priority": "low",
            "actionable": False,
            "action_state": {"recommended_action_label": "MONITOR_TRADING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
            "action_url_key": "dashboard.executions",
            "action_tab_key": "timeline",
            "action_target": "execution_timeline",
            "action_params": {"section": "trading"},
            "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
            "section_objects": {
                "state": {"state_label": "NORMAL", "severity": "info", "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.", "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요."},
                "action": {"recommended_action_label": "MONITOR_TRADING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                "route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
            },
            "updated_at": payload["last_fill_recorded_at"],
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 300,
            "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}}, "value": None},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}}, "value": None},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}}, "value": 300},
            ],
            "metrics": {
                "buy_count": 0,
                "sell_count": 0,
                "stop_loss_count": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 2500.0,
                "recent_stop_loss_reason": None,
            },
            "metric_items": [
                {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "buy_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "buy_count"}}, "value": 0},
                {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "sell_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "sell_count"}}, "value": 0},
                {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Stop Loss Count 0', "recommended_action": '손절 카운트를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "stop_loss_count", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "stop_loss_count", "highlight_reason": True}}, "value": 0},
                {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "realized_pnl"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "realized_pnl"}}, "value": 0.0},
                {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 이익 2500.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "action_target": "current_position", "action_params": {"focus_metric": "unrealized_pnl"}, "action_route": {"url_key": "dashboard.positions.current", "tab_key": "current", "target": "current_position", "params": {"focus_metric": "unrealized_pnl"}}, "value": 2500.0},
                {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Recent Stop Loss Reason 기록 없음', "recommended_action": '손절 사유 발생 여부만 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS_REASON', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}}, "value": None},
            ],
        },
        {
            "key": "learning",
            "name": "Learning",
            "state_label": "ACTIVE",
            "severity": "info",
            "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
            "state_object": {"state_label": "ACTIVE", "severity": "info", "state_message": "학습 이벤트 기록이 활성화되어 있습니다.", "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요."},
            "recommended_action_label": "MONITOR_LEARNING_SECTION",
            "action_group": "monitor",
            "action_priority": "low",
            "actionable": False,
            "action_state": {"recommended_action_label": "MONITOR_LEARNING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
            "action_url_key": "dashboard.learning",
            "action_tab_key": "recent-events",
            "action_target": "learning_recent_events",
            "action_params": {"section": "learning"},
            "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"section": "learning"}},
            "section_objects": {
                "state": {"state_label": "ACTIVE", "severity": "info", "state_message": "학습 이벤트 기록이 활성화되어 있습니다.", "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요."},
                "action": {"recommended_action_label": "MONITOR_LEARNING_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
                "route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"section": "learning"}},
            },
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 300,
            "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 300},
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}}, "value": 300},
            ],
            "metrics": {
                "last_learning_event": None,
                "learning_signal_count": 0,
                "learning_fill_count": 0,
                "last_signal_recorded_at": None,
                "last_fill_recorded_at": None,
            },
            "metric_items": [
                {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_learning_event"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_learning_event"}}, "value": None},
                {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_signal_count", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_signal_count", "event_type": "signal"}}, "value": 0},
                {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_fill_count", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_fill_count", "event_type": "fill"}}, "value": 0},
                {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}}, "value": None},
                {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}}, "value": None},
            ],
        },
        {
            "key": "recovery",
            "name": "Recovery",
            "state_label": "OK",
            "severity": "info",
            "state_message": "복구 상태가 정상입니다.",
            "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
            "state_object": {"state_label": "OK", "severity": "info", "state_message": "복구 상태가 정상입니다.", "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요."},
            "recommended_action_label": "MONITOR_RECOVERY_SECTION",
            "action_group": "monitor",
            "action_priority": "low",
            "actionable": False,
            "action_state": {"recommended_action_label": "MONITOR_RECOVERY_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
            "action_url_key": "dashboard.recovery",
            "action_tab_key": "status",
            "action_target": "recovery_status",
            "action_params": {"section": "recovery"},
            "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"section": "recovery"}},
            "section_objects": {
                "state": {"state_label": "OK", "severity": "info", "state_message": "복구 상태가 정상입니다.", "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요."},
                "action": {"recommended_action_label": "MONITOR_RECOVERY_SECTION", "action_group": "monitor", "action_priority": "low", "actionable": False},
                "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 600},
                "route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"section": "recovery"}},
            },
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 600,
            "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 600},
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}}, "value": 600},
            ],
            "metrics": {
                "safe_mode": False,
                "hard_stop": False,
                "trading_ready": True,
                "failure_stage": None,
                "last_restart_detected_at": None,
                "last_recovery_completed_at": None,
            },
            "metric_items": [
                {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "safe_mode"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "safe_mode"}}, "value": False},
                {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "hard_stop"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "hard_stop"}}, "value": False},
                {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "trading_ready"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "trading_ready"}}, "value": True},
                {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "failure_stage"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "failure_stage"}}, "value": None},
                {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}}, "value": None},
                {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}}, "value": None},
            ],
        },
        {
            "key": "promotion",
            "name": "Promotion",
            "state_label": "NOT_READY",
            "severity": "warning",
            "state_message": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
            "recommended_action": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
            "state_object": {"state_label": "NOT_READY", "severity": "warning", "state_message": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.", "recommended_action": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요."},
            "recommended_action_label": "IMPROVE_PROMOTION_SECTION",
            "action_group": "review",
            "action_priority": "high",
            "actionable": True,
            "action_state": {"recommended_action_label": "IMPROVE_PROMOTION_SECTION", "action_group": "review", "action_priority": "high", "actionable": True},
            "action_url_key": "dashboard.promotion",
            "action_tab_key": "status",
            "action_target": "promotion_status",
            "action_params": {"section": "promotion"},
            "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"section": "promotion"}},
            "section_objects": {
                "state": {"state_label": "NOT_READY", "severity": "warning", "state_message": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.", "recommended_action": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요."},
                "action": {"recommended_action_label": "IMPROVE_PROMOTION_SECTION", "action_group": "review", "action_priority": "high", "actionable": True},
                "freshness": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 86400},
                "route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"section": "promotion"}},
            },
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 86400,
            "freshness_state_object": {"updated_at": None, "stale": True, "age_sec": None, "freshness_state": "missing", "freshness_message": "데이터 없음", "freshness_label": "MISSING", "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.", "freshness_severity": "warning", "freshness_window_sec": 86400},
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}}, "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}}, "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}}, "value": 86400},
            ],
            "metrics": {
                "promotion_ready": False,
                "last_promotion_reviewed_at": None,
            },
            "metric_items": [
                {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "warning", "state_message": 'Promotion Ready 미준비', "recommended_action": '승격 기준 미달 항목을 보완하세요.', "recommended_action_label": 'IMPROVE_PROMOTION', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "promotion_ready"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "promotion_ready"}}, "value": False},
                {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "last_promotion_reviewed_at"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "last_promotion_reviewed_at"}}, "value": None},
            ],
        },
    ]})["sections"]
    assert payload["section_state_label"] == {
        "trading": "NORMAL",
        "learning": "ACTIVE",
        "recovery": "OK",
        "promotion": "NOT_READY",
    }
    assert payload["section_severity"] == {
        "trading": "info",
        "learning": "info",
        "recovery": "info",
        "promotion": "warning",
    }
    assert payload["section_state_message"] == {
        "trading": "최근 체결 기준 거래 리스크 이상이 없습니다.",
        "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
        "recovery": "복구 상태가 정상입니다.",
        "promotion": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
    }
    assert payload["section_recommended_action"] == {
        "trading": "현재 거래 섹션은 모니터링만 유지하세요.",
        "learning": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
        "recovery": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
        "promotion": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
    }


def test_dashboard_summary_facade_includes_learning_metrics(tmp_path) -> None:
    learning_service = LearningService(log_dir=tmp_path)
    learning_service.record_many(
        [
            LearningEvent(
                event_name="signal_generated",
                market="KRW-XRP",
                mode="demo",
                payload={"level": "strong"},
                recorded_at="2026-04-19T20:00:00+09:00",
            ),
            LearningEvent(
                event_name="fill_result",
                market="KRW-XRP",
                mode="demo",
                payload={"side": "buy"},
                recorded_at="2026-04-19T20:00:01+09:00",
            ),
            LearningEvent(
                event_name="restart_detected",
                market="KRW-XRP",
                mode="demo",
                payload={"app_name": "test-app"},
                recorded_at="2026-04-19T20:00:03+09:00",
            ),
            LearningEvent(
                event_name="recovery_completed",
                market="KRW-XRP",
                mode="demo",
                payload={"trading_ready": True},
                recorded_at="2026-04-19T20:00:04+09:00",
            ),
            LearningEvent(
                event_name="position_opened",
                market="KRW-XRP",
                mode="demo",
                payload={"quantity": 100.0},
                recorded_at="2026-04-19T20:00:05+09:00",
            ),
        ],
    )
    position_lifecycle_ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: "2026-04-19T20:00:02+09:00",
    )
    position_lifecycle_ledger.record(
        event_type="opened",
        position=PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=100.0,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    promotion_state_service = PromotionStateService()
    promotion_state_service.save_review(
        market="KRW-XRP",
        reviewed_at="2026-04-19T20:00:03+09:00",
        result=PromotionRunResult(
            evaluation=PromotionEvaluation(
                status="READY_FOR_REVIEW",
                approved=False,
                rejection_reasons=[],
            ),
            approval_result=PromotionApprovalResult(
                live_enabled=True,
                safe_mode_entry=True,
                reason_code=None,
            ),
        ),
    )
    facade = DashboardSummaryFacade(
        dashboard_summary_service=DashboardSummaryService(),
        promotion_dashboard_facade=PromotionDashboardFacade(
            promotion_state_service=promotion_state_service,
            promotion_dashboard_service=PromotionDashboardService(),
        ),
        learning_service=learning_service,
        position_lifecycle_ledger=position_lifecycle_ledger,
        timestamp_provider=lambda: "2026-04-19T20:05:00+09:00",
    )
    boot_state = BootState(
        safe_mode=False,
        hard_stop=False,
        trading_ready=True,
        failure_stage=None,
        portfolio_state=PortfolioState(
            cash_balance=250000.0,
            asset_currency="XRP",
            asset_balance=0.0,
            avg_buy_price=0.0,
        ),
        reconcile_result={"open_order_count": 0},
    )

    payload = facade.build_response(
        boot_state=boot_state,
        trading_mode="demo",
        learning_enabled=True,
    )

    assert payload["last_learning_event"] == "position_opened"
    assert payload["learning_signal_count"] == 1
    assert payload["learning_fill_count"] == 1
    assert payload["last_signal_recorded_at"] is not None
    assert payload["last_fill_recorded_at"] is not None
    assert payload["last_position_event"] == "opened"
    assert payload["last_promotion_reviewed_at"] == "2026-04-19T20:00:03+09:00"
    assert payload["last_restart_detected_at"] is not None
    assert payload["last_recovery_completed_at"] is not None
    sections = {section["key"]: section for section in payload["sections"]}
    assert set(sections) == {"trading", "learning", "recovery", "promotion"}
    assert sections["trading"]["action_route"] == {
        "url_key": "dashboard.executions",
        "tab_key": "timeline",
        "target": "execution_timeline",
        "params": {"section": "trading"},
    }
    assert sections["trading"]["updated_at"] == payload["last_fill_recorded_at"]
    assert sections["trading"]["freshness_state"] == "fresh"
    assert sections["learning"]["action_route"] == {
        "url_key": "dashboard.learning",
        "tab_key": "recent-events",
        "target": "learning_recent_events",
        "params": {"section": "learning"},
    }
    assert sections["learning"]["updated_at"] == payload["last_fill_recorded_at"]
    assert sections["learning"]["freshness_state"] == "fresh"
    assert sections["learning"]["metrics"]["last_learning_event"] == "position_opened"
    assert sections["learning"]["metrics"]["learning_signal_count"] == 1
    assert sections["learning"]["metrics"]["learning_fill_count"] == 1
    assert sections["recovery"]["action_route"] == {
        "url_key": "dashboard.recovery",
        "tab_key": "status",
        "target": "recovery_status",
        "params": {"section": "recovery"},
    }
    assert sections["promotion"]["action_route"] == {
        "url_key": "dashboard.promotion",
        "tab_key": "status",
        "target": "promotion_status",
        "params": {"section": "promotion"},
    }
    assert payload["section_state_label"] == {
        "trading": "NORMAL",
        "learning": "ACTIVE",
        "recovery": "OK",
        "promotion": "READY",
    }
    assert payload["section_severity"] == {
        "trading": "info",
        "learning": "info",
        "recovery": "info",
        "promotion": "info",
    }
    assert payload["section_state_message"] == {
        "trading": "최근 체결 기준 거래 리스크 이상이 없습니다.",
        "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
        "recovery": "복구 상태가 정상입니다.",
        "promotion": "실거래 승격 검토 준비가 완료되었습니다.",
    }
    assert payload["section_recommended_action"] == {
        "trading": "현재 거래 섹션은 모니터링만 유지하세요.",
        "learning": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
        "recovery": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
        "promotion": "승격 검토 또는 수동 승인 절차를 진행하세요.",
    }
