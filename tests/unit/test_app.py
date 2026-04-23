from fastapi.testclient import TestClient

from app.main import create_app
from app.services.learning.service import LearningEvent
from app.services.promotion.approval import PromotionApprovalResult
from app.services.promotion.evaluator import PromotionEvaluation
from app.services.promotion.runner import PromotionRunResult


class BootNotificationDispatcherStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def dispatch_boot_event(self, **kwargs) -> None:
        self.calls.append(kwargs)


class SummaryStubService:
    def build(self, **kwargs):
        payload = {
            "coin_balance": 180.5,
            "cash_balance": 250000.0,
            "realized_pnl": 12500.0,
            "unrealized_pnl": -3200.0,
            "buy_count": 4,
            "sell_count": 3,
            "stop_loss_count": 1,
            "recent_stop_loss_reason": "STOP_LOSS_PRICE_HIT",
            "trading_mode": "demo",
            "learning_enabled": True,
            "last_learning_event": "position_opened",
            "learning_signal_count": 3,
            "learning_fill_count": 2,
            "last_signal_recorded_at": "2026-04-19T20:00:00+09:00",
            "last_fill_recorded_at": "2026-04-19T20:00:01+09:00",
            "last_position_event": "opened",
            "last_promotion_reviewed_at": "2026-04-19T20:00:02+09:00",
            "last_restart_detected_at": "2026-04-19T20:00:03+09:00",
            "last_recovery_completed_at": "2026-04-19T20:00:04+09:00",
            "sections": [
                {
                    "key": "trading",
                    "name": "Trading",
                    "state_label": "STOP_LOSS_TRIGGERED",
                    "severity": "critical",
                    "state_message": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
                    "recommended_action": "최근 손절 발생 원인과 청산 흐름을 점검하세요.",
                    "state_object": {"state_label": "STOP_LOSS_TRIGGERED", "severity": "critical", "state_message": "최근 손절 사유: STOP_LOSS_PRICE_HIT", "recommended_action": "최근 손절 발생 원인과 청산 흐름을 점검하세요."},
                    "recommended_action_label": "REVIEW_TRADING_SECTION",
                    "action_group": "review",
                    "action_priority": "high",
                    "actionable": True,
                    "action_state": {"recommended_action_label": "REVIEW_TRADING_SECTION", "action_group": "review", "action_priority": "high", "actionable": True},
                    "action_url_key": "dashboard.executions",
                    "action_tab_key": "timeline",
                    "action_target": "execution_timeline",
                    "action_params": {"section": "trading"},
                    "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
                    "section_objects": {
                        "state": {"state_label": "STOP_LOSS_TRIGGERED", "severity": "critical", "state_message": "최근 손절 사유: STOP_LOSS_PRICE_HIT", "recommended_action": "최근 손절 발생 원인과 청산 흐름을 점검하세요."},
                        "action": {"recommended_action_label": "REVIEW_TRADING_SECTION", "action_group": "review", "action_priority": "high", "actionable": True},
                        "freshness": {"updated_at": "2026-04-19T20:00:01+09:00", "stale": False, "age_sec": 299, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 300},
                        "route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"section": "trading"}},
                    },
                    "updated_at": "2026-04-19T20:00:01+09:00",
                    "stale": False,
                    "age_sec": 299,
                    "freshness_state": "fresh",
                    "freshness_message": "최근 데이터",
                    "freshness_label": "RECENT",
                    "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                    "freshness_severity": "info",
                    "freshness_window_sec": 300,
                    "freshness_state_object": {"updated_at": "2026-04-19T20:00:01+09:00", "stale": False, "age_sec": 299, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 300},
                    "freshness_metric_items": [
                        {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T20:00:01+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "updated_at", "section": "trading", "kind": "freshness"}}, "value": "2026-04-19T20:00:01+09:00"},
                        {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 299', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "age_sec", "section": "trading", "kind": "freshness"}}, "value": 299},
                        {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "action_target": "market_overview", "action_params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}, "action_route": {"url_key": "dashboard.market", "tab_key": "overview", "target": "market_overview", "params": {"focus_metric": "freshness_window_sec", "section": "trading", "kind": "freshness"}}, "value": 300},
                    ],
                    "metrics": {
                        "buy_count": 4,
                        "sell_count": 3,
                        "stop_loss_count": 1,
                        "realized_pnl": 12500.0,
                        "unrealized_pnl": -3200.0,
                        "recent_stop_loss_reason": "STOP_LOSS_PRICE_HIT",
                    },
                    "metric_items": [
                        {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 4', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "buy_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "buy_count"}}, "value": 4},
                        {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 3', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "sell_count"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "sell_count"}}, "value": 3},
                        {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "critical", "state_message": 'Stop Loss Count 1', "recommended_action": '최근 손절 흐름과 청산 원인을 점검하세요.', "recommended_action_label": 'REVIEW_STOP_LOSS', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "stop_loss_count", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "stop_loss_count", "highlight_reason": True}}, "value": 1},
                        {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 이익 12500.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "action_target": "execution_timeline", "action_params": {"focus_metric": "realized_pnl"}, "action_route": {"url_key": "dashboard.executions", "tab_key": "timeline", "target": "execution_timeline", "params": {"focus_metric": "realized_pnl"}}, "value": 12500.0},
                        {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "warning", "state_message": 'Unrealized PnL 손실 -3200.0', "recommended_action": '손익 악화 원인과 리스크 설정을 점검하세요.', "recommended_action_label": 'REVIEW_PNL', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "action_target": "current_position", "action_params": {"focus_metric": "unrealized_pnl"}, "action_route": {"url_key": "dashboard.positions.current", "tab_key": "current", "target": "current_position", "params": {"focus_metric": "unrealized_pnl"}}, "value": -3200.0},
                        {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "critical", "state_message": 'Recent Stop Loss Reason STOP_LOSS_PRICE_HIT', "recommended_action": '최근 손절 사유를 검토하고 재진입 조건을 점검하세요.', "recommended_action_label": 'REVIEW_STOP_LOSS_REASON', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "action_target": "position_history", "action_params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}, "action_route": {"url_key": "dashboard.positions.history", "tab_key": "history", "target": "position_history", "params": {"focus_metric": "recent_stop_loss_reason", "highlight_reason": True}}, "value": "STOP_LOSS_PRICE_HIT"},
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
                        "freshness": {"updated_at": "2026-04-19T20:00:01+09:00", "stale": False, "age_sec": 299, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 300},
                        "route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"section": "learning"}},
                    },
                    "updated_at": "2026-04-19T20:00:01+09:00",
                    "stale": False,
                    "age_sec": 299,
                    "freshness_state": "fresh",
                    "freshness_message": "최근 데이터",
                    "freshness_label": "RECENT",
                    "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                    "freshness_severity": "info",
                    "freshness_window_sec": 300,
                    "freshness_state_object": {"updated_at": "2026-04-19T20:00:01+09:00", "stale": False, "age_sec": 299, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 300},
                    "freshness_metric_items": [
                        {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T20:00:01+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "updated_at", "section": "learning", "kind": "freshness"}}, "value": "2026-04-19T20:00:01+09:00"},
                        {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 299', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "age_sec", "section": "learning", "kind": "freshness"}}, "value": 299},
                        {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "freshness_window_sec", "section": "learning", "kind": "freshness"}}, "value": 300},
                    ],
                    "metrics": {
                        "last_learning_event": "position_opened",
                        "learning_signal_count": 3,
                        "learning_fill_count": 2,
                        "last_signal_recorded_at": "2026-04-19T20:00:00+09:00",
                        "last_fill_recorded_at": "2026-04-19T20:00:01+09:00",
                    },
                    "metric_items": [
                        {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event position_opened', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_learning_event"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_learning_event"}}, "value": "position_opened"},
                        {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 3', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_signal_count", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_signal_count", "event_type": "signal"}}, "value": 3},
                        {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 2', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "learning_fill_count", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "learning_fill_count", "event_type": "fill"}}, "value": 2},
                        {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 2026-04-19T20:00:00+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_signal_recorded_at", "event_type": "signal"}}, "value": "2026-04-19T20:00:00+09:00"},
                        {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 2026-04-19T20:00:01+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "action_target": "learning_recent_events", "action_params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}, "action_route": {"url_key": "dashboard.learning", "tab_key": "recent-events", "target": "learning_recent_events", "params": {"focus_metric": "last_fill_recorded_at", "event_type": "fill"}}, "value": "2026-04-19T20:00:01+09:00"},
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
                        "freshness": {"updated_at": "2026-04-19T20:00:04+09:00", "stale": False, "age_sec": 296, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 600},
                        "route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"section": "recovery"}},
                    },
                    "updated_at": "2026-04-19T20:00:04+09:00",
                    "stale": False,
                    "age_sec": 296,
                    "freshness_state": "fresh",
                    "freshness_message": "최근 데이터",
                    "freshness_label": "RECENT",
                    "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                    "freshness_severity": "info",
                    "freshness_window_sec": 600,
                    "freshness_state_object": {"updated_at": "2026-04-19T20:00:04+09:00", "stale": False, "age_sec": 296, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 600},
                    "freshness_metric_items": [
                        {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T20:00:04+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "updated_at", "section": "recovery", "kind": "freshness"}}, "value": "2026-04-19T20:00:04+09:00"},
                        {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 296', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "age_sec", "section": "recovery", "kind": "freshness"}}, "value": 296},
                        {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "freshness_window_sec", "section": "recovery", "kind": "freshness"}}, "value": 600},
                    ],
                    "metrics": {
                        "safe_mode": False,
                        "hard_stop": False,
                        "trading_ready": True,
                        "failure_stage": None,
                        "last_restart_detected_at": "2026-04-19T20:00:03+09:00",
                        "last_recovery_completed_at": "2026-04-19T20:00:04+09:00",
                    },
                    "metric_items": [
                        {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "safe_mode"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "safe_mode"}}, "value": False},
                        {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "hard_stop"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "hard_stop"}}, "value": False},
                        {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "trading_ready"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "trading_ready"}}, "value": True},
                        {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "action_target": "recovery_status", "action_params": {"focus_metric": "failure_stage"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "status", "target": "recovery_status", "params": {"focus_metric": "failure_stage"}}, "value": None},
                        {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 2026-04-19T20:00:03+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_restart_detected_at", "event_type": "restart_detected"}}, "value": "2026-04-19T20:00:03+09:00"},
                        {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 2026-04-19T20:00:04+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "action_target": "recovery_timeline", "action_params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}, "action_route": {"url_key": "dashboard.recovery", "tab_key": "timeline", "target": "recovery_timeline", "params": {"focus_metric": "last_recovery_completed_at", "event_type": "recovery_completed"}}, "value": "2026-04-19T20:00:04+09:00"},
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
                        "freshness": {"updated_at": "2026-04-19T20:00:02+09:00", "stale": False, "age_sec": 298, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 86400},
                        "route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"section": "promotion"}},
                    },
                    "updated_at": "2026-04-19T20:00:02+09:00",
                    "stale": False,
                    "age_sec": 298,
                    "freshness_state": "fresh",
                    "freshness_message": "최근 데이터",
                    "freshness_label": "RECENT",
                    "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                    "freshness_severity": "info",
                    "freshness_window_sec": 86400,
                    "freshness_state_object": {"updated_at": "2026-04-19T20:00:02+09:00", "stale": False, "age_sec": 298, "freshness_state": "fresh", "freshness_message": "최근 데이터", "freshness_label": "RECENT", "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.", "freshness_severity": "info", "freshness_window_sec": 86400},
                    "freshness_metric_items": [
                        {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T20:00:02+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "updated_at", "section": "promotion", "kind": "freshness"}}, "value": "2026-04-19T20:00:02+09:00"},
                        {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 298', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "age_sec", "section": "promotion", "kind": "freshness"}}, "value": 298},
                        {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "freshness_window_sec", "section": "promotion", "kind": "freshness"}}, "value": 86400},
                    ],
                    "metrics": {
                        "promotion_ready": False,
                        "last_promotion_reviewed_at": "2026-04-19T20:00:02+09:00",
                    },
                    "metric_items": [
                        {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "warning", "state_message": 'Promotion Ready 미준비', "recommended_action": '승격 기준 미달 항목을 보완하세요.', "recommended_action_label": 'IMPROVE_PROMOTION', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "promotion_ready"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "promotion_ready"}}, "value": False},
                        {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 2026-04-19T20:00:02+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "action_target": "promotion_status", "action_params": {"focus_metric": "last_promotion_reviewed_at"}, "action_route": {"url_key": "dashboard.promotion", "tab_key": "status", "target": "promotion_status", "params": {"focus_metric": "last_promotion_reviewed_at"}}, "value": "2026-04-19T20:00:02+09:00"},
                    ],
                },
            ],
            "section_state_label": {
                "trading": "STOP_LOSS_TRIGGERED",
                "learning": "ACTIVE",
                "recovery": "OK",
                "promotion": "NOT_READY",
            },
            "section_severity": {
                "trading": "critical",
                "learning": "info",
                "recovery": "info",
                "promotion": "warning",
            },
            "section_state_message": {
                "trading": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
                "learning": "학습 이벤트 기록이 활성화되어 있습니다.",
                "recovery": "복구 상태가 정상입니다.",
                "promotion": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
            },
            "section_recommended_action": {
                "trading": "최근 손절 발생 원인과 청산 흐름을 점검하세요.",
                "learning": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
                "recovery": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
                "promotion": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
            },
            "safe_mode": False,
            "hard_stop": False,
            "trading_ready": True,
            "promotion_ready": False,
        }
        for section in payload["sections"]:
            section["card_object"] = {
                "state": section["section_objects"]["state"],
                "action": section["section_objects"]["action"],
                "freshness": section["section_objects"]["freshness"],
                "route": section["section_objects"]["route"],
                "metrics": section["metrics"],
                "metric_items": section["metric_items"],
                "freshness_metric_items": section["freshness_metric_items"],
            }
        payload["cards"] = [
            {
                "key": section["key"],
                "name": section["name"],
                "card": section["card_object"],
                "state": section["state_object"],
                "action": section["action_state"],
                "freshness": section["freshness_state_object"],
                "route": section["action_route"],
            }
            for section in payload["sections"]
        ]
        payload["card_map"] = {card["key"]: card for card in payload["cards"]}
        payload["card_order"] = [card["key"] for card in payload["cards"]]
        severity_counts = {"info": 0, "warning": 0, "critical": 0}
        actionable_count = 0
        stale_count = 0
        for card in payload["cards"]:
            severity = card["state"]["severity"]
            if severity in severity_counts:
                severity_counts[severity] += 1
            if card["action"]["actionable"]:
                actionable_count += 1
            if card["freshness"]["stale"]:
                stale_count += 1
        payload["card_meta"] = {
            "count": len(payload["cards"]),
            "keys": [card["key"] for card in payload["cards"]],
            "severity_counts": severity_counts,
            "actionable_count": actionable_count,
            "stale_count": stale_count,
        }
        payload["summary_object"] = {
            "coin_balance": payload.get("coin_balance"),
            "cash_balance": payload.get("cash_balance"),
            "realized_pnl": payload.get("realized_pnl"),
            "unrealized_pnl": payload.get("unrealized_pnl"),
            "buy_count": payload.get("buy_count"),
            "sell_count": payload.get("sell_count"),
            "stop_loss_count": payload.get("stop_loss_count"),
            "recent_stop_loss_reason": payload.get("recent_stop_loss_reason"),
            "trading_mode": payload.get("trading_mode"),
            "learning_enabled": payload.get("learning_enabled"),
            "promotion_ready": payload.get("promotion_ready"),
            "safe_mode": payload.get("safe_mode"),
            "hard_stop": payload.get("hard_stop"),
            "trading_ready": payload.get("trading_ready"),
        }
        payload["cards_object"] = {
            "cards": payload["cards"],
            "card_map": payload["card_map"],
            "card_order": payload["card_order"],
            "card_meta": payload["card_meta"],
        }
        payload["dashboard_meta"] = {
            "section_count": len(payload["sections"]),
            "card_count": len(payload["cards"]),
            "section_keys": [section["key"] for section in payload["sections"]],
            "card_keys": [card["key"] for card in payload["cards"]],
            "severity_counts": {
                "info": sum(1 for section in payload["sections"] if section["severity"] == "info"),
                "warning": sum(1 for section in payload["sections"] if section["severity"] == "warning"),
                "critical": sum(1 for section in payload["sections"] if section["severity"] == "critical"),
            },
            "actionable_section_count": sum(
                1 for section in payload["sections"] if section["actionable"]
            ),
            "actionable_section_keys": [
                section["key"] for section in payload["sections"] if section["actionable"]
            ],
            "freshness_counts": {
                "fresh": sum(1 for section in payload["sections"] if section["freshness_state"] == "fresh"),
                "stale": sum(1 for section in payload["sections"] if section["freshness_state"] == "stale"),
                "missing": sum(1 for section in payload["sections"] if section["freshness_state"] == "missing"),
            },
            "stale_section_count": sum(
                1 for section in payload["sections"] if section["stale"]
            ),
            "stale_section_keys": [
                section["key"] for section in payload["sections"] if section["stale"]
            ],
            "meta_object": {
                "counts": {
                    "section_count": len(payload["sections"]),
                    "card_count": len(payload["cards"]),
                    "actionable_section_count": sum(
                        1 for section in payload["sections"] if section["actionable"]
                    ),
                    "stale_section_count": sum(
                        1 for section in payload["sections"] if section["stale"]
                    ),
                },
                "keys": {
                    "section_keys": [section["key"] for section in payload["sections"]],
                    "card_keys": [card["key"] for card in payload["cards"]],
                    "actionable_section_keys": [
                        section["key"] for section in payload["sections"] if section["actionable"]
                    ],
                    "stale_section_keys": [
                        section["key"] for section in payload["sections"] if section["stale"]
                    ],
                },
                "severity_counts": {
                    "info": sum(1 for section in payload["sections"] if section["severity"] == "info"),
                    "warning": sum(1 for section in payload["sections"] if section["severity"] == "warning"),
                    "critical": sum(1 for section in payload["sections"] if section["severity"] == "critical"),
                },
                "freshness_counts": {
                    "fresh": sum(1 for section in payload["sections"] if section["freshness_state"] == "fresh"),
                    "stale": sum(1 for section in payload["sections"] if section["freshness_state"] == "stale"),
                    "missing": sum(1 for section in payload["sections"] if section["freshness_state"] == "missing"),
                },
            },
        }
        payload["dashboard_order"] = ["summary", "cards", "meta"]
        payload["dashboard_labels"] = {
            "summary": "Summary",
            "cards": "Cards",
            "meta": "Meta",
        }
        payload["dashboard_panels"] = [
            {
                "key": "summary",
                "label": payload["dashboard_labels"]["summary"],
                "data": payload["summary_object"],
            },
            {
                "key": "cards",
                "label": payload["dashboard_labels"]["cards"],
                "data": payload["cards_object"],
            },
            {
                "key": "meta",
                "label": payload["dashboard_labels"]["meta"],
                "data": payload["dashboard_meta"],
            },
        ]
        payload["dashboard_panel_map"] = {
            panel["key"]: panel
            for panel in payload["dashboard_panels"]
        }
        payload["dashboard_panel_meta"] = {
            "count": len(payload["dashboard_panels"]),
            "keys": [panel["key"] for panel in payload["dashboard_panels"]],
            "label_map": {
                panel["key"]: panel["label"]
                for panel in payload["dashboard_panels"]
            },
            "order_map": {
                panel["key"]: index
                for index, panel in enumerate(payload["dashboard_panels"])
            },
            "meta_object": {
                "count": len(payload["dashboard_panels"]),
                "keys": [panel["key"] for panel in payload["dashboard_panels"]],
                "label_map": {
                    panel["key"]: panel["label"]
                    for panel in payload["dashboard_panels"]
                },
                "order_map": {
                    panel["key"]: index
                    for index, panel in enumerate(payload["dashboard_panels"])
                },
            },
        }
        payload["dashboard_navigation"] = {
            "order": payload["dashboard_order"],
            "labels": payload["dashboard_labels"],
            "panels": [
                {
                    "key": panel["key"],
                    "label": panel["label"],
                    "index": index,
                }
                for index, panel in enumerate(payload["dashboard_panels"])
            ],
        }
        payload["dashboard_navigation_items"] = payload["dashboard_navigation"]["panels"]
        payload["dashboard_navigation_map"] = {
            panel["key"]: panel
            for panel in payload["dashboard_navigation"]["panels"]
        }
        payload["dashboard_navigation_meta"] = {
            "count": len(payload["dashboard_navigation"]["panels"]),
            "keys": [
                panel["key"]
                for panel in payload["dashboard_navigation"]["panels"]
            ],
            "label_map": {
                panel["key"]: panel["label"]
                for panel in payload["dashboard_navigation"]["panels"]
            },
            "order_map": {
                panel["key"]: index
                for index, panel in enumerate(payload["dashboard_navigation"]["panels"])
            },
            "item_map": {
                panel["key"]: {
                    "label": panel["label"],
                    "index": index,
                }
                for index, panel in enumerate(payload["dashboard_navigation"]["panels"])
            },
            "meta_object": {
                "count": len(payload["dashboard_navigation"]["panels"]),
                "keys": [
                    panel["key"]
                    for panel in payload["dashboard_navigation"]["panels"]
                ],
                "label_map": {
                    panel["key"]: panel["label"]
                    for panel in payload["dashboard_navigation"]["panels"]
                },
                "order_map": {
                    panel["key"]: index
                    for index, panel in enumerate(payload["dashboard_navigation"]["panels"])
                },
                "item_map": {
                    panel["key"]: {
                        "label": panel["label"],
                        "index": index,
                    }
                    for index, panel in enumerate(payload["dashboard_navigation"]["panels"])
                },
            },
        }
        payload["dashboard_navigation_object"] = {
            "navigation": payload["dashboard_navigation"],
            "items": payload["dashboard_navigation_items"],
            "navigation_map": payload["dashboard_navigation_map"],
            "navigation_meta": payload["dashboard_navigation_meta"],
        }
        payload["dashboard_structure"] = {
            "order": payload["dashboard_order"],
            "labels": payload["dashboard_labels"],
            "panels": payload["dashboard_panels"],
            "panel_map": payload["dashboard_panel_map"],
            "panel_meta": payload["dashboard_panel_meta"],
            "navigation": payload["dashboard_navigation"],
            "navigation_items": payload["dashboard_navigation_items"],
            "navigation_map": payload["dashboard_navigation_map"],
            "navigation_meta": payload["dashboard_navigation_meta"],
            "navigation_object": payload["dashboard_navigation_object"],
        }
        payload["dashboard_structure_meta"] = {
            "keys": list(payload["dashboard_structure"].keys()),
            "count": len(payload["dashboard_structure"]),
        }
        payload["dashboard_structure_meta_object"] = {
            "meta": payload["dashboard_structure_meta"],
        }
        payload["dashboard_structure_map"] = {
            key: payload["dashboard_structure"][key]
            for key in payload["dashboard_structure"]
        }
        payload["dashboard_structure_items"] = [
            {
                "key": key,
                "value": payload["dashboard_structure"][key],
            }
            for key in payload["dashboard_structure"]
        ]
        payload["dashboard_structure_item_map"] = {
            item["key"]: item
            for item in payload["dashboard_structure_items"]
        }
        payload["dashboard_structure_item_index_map"] = {
            item["key"]: index
            for index, item in enumerate(payload["dashboard_structure_items"])
        }
        payload["dashboard_structure_item_order"] = [
            item["key"] for item in payload["dashboard_structure_items"]
        ]
        payload["dashboard_structure_item_meta"] = {
            "count": len(payload["dashboard_structure_items"]),
            "keys": payload["dashboard_structure_item_order"],
            "index_map": payload["dashboard_structure_item_index_map"],
        }
        payload["dashboard_structure_item_meta_object"] = {
            "meta": payload["dashboard_structure_item_meta"],
        }
        payload["dashboard_structure_item_lookup_object"] = {
            "item_map": payload["dashboard_structure_item_map"],
            "item_index_map": payload["dashboard_structure_item_index_map"],
        }
        payload["dashboard_structure_items_object"] = {
            "items": payload["dashboard_structure_items"],
            "item_map": payload["dashboard_structure_item_map"],
            "item_index_map": payload["dashboard_structure_item_index_map"],
            "lookup": payload["dashboard_structure_item_lookup_object"],
            "item_order": payload["dashboard_structure_item_order"],
            "item_meta": payload["dashboard_structure_item_meta"],
            "item_meta_object": payload["dashboard_structure_item_meta_object"],
        }
        payload["dashboard_structure_object"] = {
            "structure": payload["dashboard_structure"],
            "meta": payload["dashboard_structure_meta"],
            "meta_object": payload["dashboard_structure_meta_object"],
            "structure_map": payload["dashboard_structure_map"],
            "items": payload["dashboard_structure_items"],
            "item_map": payload["dashboard_structure_item_map"],
            "item_order": payload["dashboard_structure_item_order"],
            "item_meta": payload["dashboard_structure_item_meta"],
            "item_meta_object": payload["dashboard_structure_item_meta_object"],
            "items_object": payload["dashboard_structure_items_object"],
        }
        payload["dashboard_object"] = {
            "summary": payload["summary_object"],
            "cards": payload["cards_object"],
            "meta": payload["dashboard_meta"],
            "order": payload["dashboard_order"],
            "labels": payload["dashboard_labels"],
            "panels": payload["dashboard_panels"],
            "panel_map": payload["dashboard_panel_map"],
            "panel_meta": payload["dashboard_panel_meta"],
            "navigation": payload["dashboard_navigation"],
            "navigation_map": payload["dashboard_navigation_map"],
            "navigation_meta": payload["dashboard_navigation_meta"],
            "navigation_object": payload["dashboard_navigation_object"],
            "structure": payload["dashboard_structure"],
            "structure_meta": payload["dashboard_structure_meta"],
            "structure_meta_object": payload["dashboard_structure_meta_object"],
            "structure_map": payload["dashboard_structure_map"],
            "structure_items": payload["dashboard_structure_items"],
            "structure_item_map": payload["dashboard_structure_item_map"],
            "structure_item_index_map": payload["dashboard_structure_item_index_map"],
            "structure_item_lookup_object": payload["dashboard_structure_item_lookup_object"],
            "structure_item_order": payload["dashboard_structure_item_order"],
            "structure_item_meta": payload["dashboard_structure_item_meta"],
            "structure_item_meta_object": payload["dashboard_structure_item_meta_object"],
            "structure_items_object": payload["dashboard_structure_items_object"],
            "structure_object": payload["dashboard_structure_object"],
        }
        return payload


class PromotionRunnerStub:
    def __init__(self, result: PromotionRunResult) -> None:
        self.result = result
        self.requests: list[object] = []

    def run(self, request) -> PromotionRunResult:
        self.requests.append(request)
        return self.result


class LearningServiceStub:
    def __init__(self) -> None:
        self.events: list[LearningEvent] = []

    def record(self, event: LearningEvent) -> None:
        self.events.append(event)

    def recent_events(self, *, limit: int | None = None) -> list[LearningEvent]:
        if limit is None or limit >= len(self.events):
            return list(self.events)
        return self.events[-limit:]


class TelegramNotifierStub:
    def __init__(self) -> None:
        self.fills = []

    def notify_fill(self, fill) -> None:
        self.fills.append(fill)


class TradeDecisionServiceStub:
    def evaluate(self, request):
        self.request = request
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        }


class TradeExecutionServiceStub:
    def execute(self, decision):
        self.decision = decision
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "status": "filled",
            "blocked_reason": None,
            "execution": {
                "market": "KRW-XRP",
                "side": "buy",
                "filled_price": 800.0,
                "filled_quantity": 192.5,
                "mode": "demo",
                "is_virtual": True,
            },
        }


class PostFillServiceStub:
    def process(self, execution_result):
        self.execution_result = execution_result
        return self

    @staticmethod
    def to_payload(result) -> dict[str, object]:
        return {
            "execution": {
                "status": "filled",
                "blocked_reason": None,
                "execution": {
                    "market": "KRW-XRP",
                    "side": "buy",
                    "filled_price": 800.0,
                    "filled_quantity": 192.5,
                    "mode": "demo",
                    "is_virtual": True,
                },
            },
            "position": {
                "market": "KRW-XRP",
                "signal_level": "strong",
                "entry_price": 800.0,
                "quantity": 192.5,
                "stop_loss_price": 785.6,
                "stop_loss_pct": 0.018,
                "validation_window_sec": 180,
                "min_expected_return_pct": 0.004,
                "stop_loss_reason": None,
            },
        }


def test_health_endpoint_reports_valid_mode(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "demo",
        "learning_enabled": True,
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "failure_stage": None,
    }


def test_summary_endpoint_returns_dashboard_panel_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            dashboard_summary_service=SummaryStubService(),
        ),
    )

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    expected = SummaryStubService().build()
    expected.update(
        {
            "safe_mode": False,
            "hard_stop": False,
            "trading_ready": True,
            "promotion_ready": False,
        },
    )
    assert response.json() == expected


def test_decision_entry_endpoint_returns_trade_decision_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    trade_decision_service = TradeDecisionServiceStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_decision_service=trade_decision_service,
        ),
    )

    response = client.post(
        "/decision/entry",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "decision": {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        },
    }


def test_decision_execute_endpoint_returns_execution_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    trade_decision_service = TradeDecisionServiceStub()
    trade_execution_service = TradeExecutionServiceStub()
    post_fill_service = PostFillServiceStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_decision_service=trade_decision_service,
            trade_execution_service=trade_execution_service,
            post_fill_service=post_fill_service,
        ),
    )

    response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "decision": {
            "features": {"ret_1s": 0.001},
            "signal": {"level": "strong", "blocked": False},
            "regime": {"label": "risk_on", "entry_allowed": True},
            "sizing": {"allowed": True, "buy_amount": 154000.0},
        },
        "execution": {
            "status": "filled",
            "blocked_reason": None,
            "execution": {
                "market": "KRW-XRP",
                "side": "buy",
                "filled_price": 800.0,
                "filled_quantity": 192.5,
                "mode": "demo",
                "is_virtual": True,
            },
        },
        "post_fill": {
            "execution": {
                "status": "filled",
                "blocked_reason": None,
                "execution": {
                    "market": "KRW-XRP",
                    "side": "buy",
                    "filled_price": 800.0,
                    "filled_quantity": 192.5,
                    "mode": "demo",
                    "is_virtual": True,
                },
            },
            "position": {
                "market": "KRW-XRP",
                "signal_level": "strong",
                "entry_price": 800.0,
                "quantity": 192.5,
                "stop_loss_price": 785.6,
                "stop_loss_pct": 0.018,
                "validation_window_sec": 180,
                "min_expected_return_pct": 0.004,
                "stop_loss_reason": None,
            },
        },
    }


def test_decision_execute_notifies_buy_fill(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    trade_fill_notifier = TelegramNotifierStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            trade_fill_notifier=trade_fill_notifier,
        ),
    )

    response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )

    assert response.status_code == 200
    assert len(trade_fill_notifier.fills) == 1
    assert trade_fill_notifier.fills[0].side == "buy"
    assert trade_fill_notifier.fills[0].is_stop_loss is False


def test_position_endpoints_return_saved_position_and_overlay(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
        ),
    )

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    position_response = client.get("/position/current")
    overlay_response = client.get("/position/overlay/stop-loss")

    assert position_response.status_code == 200
    assert overlay_response.status_code == 200
    assert position_response.json()["status"] == "ok"
    assert position_response.json()["position"]["market"] == "KRW-XRP"
    assert overlay_response.json() == {
        "status": "ok",
        "overlay": {
            "active": True,
            "market": "KRW-XRP",
            "stop_loss_price": position_response.json()["position"]["stop_loss_price"],
            "label": "STOP LOSS",
        },
    }

    risk_response = client.post(
        "/position/risk-check",
        json={
            "current_price": position_response.json()["position"]["stop_loss_price"] - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert risk_response.status_code == 200
    assert risk_response.json()["status"] == "ok"
    assert risk_response.json()["hard_stop"]["triggered"] is True
    assert (
        risk_response.json()["post_entry"]["reason_code"]
        == "STOP_LOSS_EXPECTATION_FAILED"
    )

    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": position_response.json()["position"]["stop_loss_price"] - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert exit_response.status_code == 200
    assert exit_response.json()["status"] == "ok"
    assert exit_response.json()["trigger"] == {
        "type": "hard_stop",
        "reason_code": "STOP_LOSS_PRICE_HIT",
        "exit_ratio": 1.0,
    }
    assert exit_response.json()["execution"]["side"] == "sell"
    assert exit_response.json()["execution"]["is_stop_loss"] is True
    assert client.get("/position/current").json() == {
        "status": "empty",
        "position": None,
    }


def test_position_exit_records_learning_event_and_notifies_fill(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    learning_service = LearningServiceStub()
    trade_fill_notifier = TelegramNotifierStub()

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            learning_service=learning_service,
            trade_fill_notifier=trade_fill_notifier,
        ),
    )

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )

    assert exit_response.status_code == 200
    assert len(trade_fill_notifier.fills) == 2
    assert trade_fill_notifier.fills[0].side == "buy"
    assert trade_fill_notifier.fills[-1].side == "sell"
    assert trade_fill_notifier.fills[-1].is_stop_loss is True
    assert [event.event_name for event in learning_service.events][-4:] == [
        "position_opened",
        "fill_result",
        "position_exit_completed",
        "position_lifecycle_updated",
    ]
    assert learning_service.events[-2].payload["trigger_type"] == "hard_stop"
    assert learning_service.events[-1].payload["event_type"] == "closed"


def test_summary_endpoint_reflects_runtime_execution_counts(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    summary_response = client.get("/dashboard/summary")

    assert summary_response.status_code == 200
    assert summary_response.json()["buy_count"] == 1
    assert summary_response.json()["sell_count"] == 1
    assert summary_response.json()["stop_loss_count"] == 1
    assert summary_response.json()["recent_stop_loss_reason"] == "STOP_LOSS_PRICE_HIT"
    assert summary_response.json()["realized_pnl"] < 0.0
    assert summary_response.json()["section_severity"]["trading"] == "critical"


def test_summary_endpoint_reflects_unrealized_pnl_from_latest_price(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    risk_response = client.post(
        "/position/risk-check",
        json={
            "current_price": 845.0,
            "elapsed_sec": 60,
            "momentum_score": 0.6,
            "orderbook_imbalance": 0.1,
        },
    )
    assert risk_response.status_code == 200

    summary_response = client.get("/dashboard/summary")

    assert summary_response.status_code == 200
    assert summary_response.json()["unrealized_pnl"] > 0.0
    assert summary_response.json()["section_severity"]["trading"] == "info"


def test_market_current_endpoint_returns_latest_snapshot(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:10:00+09:00",
        ),
    )

    empty_response = client.get("/market/current")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "snapshot": None,
    }

    entry_response = client.post(
        "/decision/entry",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert entry_response.status_code == 200

    current_response = client.get("/market/current")

    assert current_response.status_code == 200
    assert current_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "snapshot": {
            "market": "KRW-XRP",
            "price": 820.0,
            "recorded_at": "2026-04-19T20:10:00+09:00",
        },
    }


def test_market_history_endpoint_returns_recent_snapshots(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    timestamps = iter(
        [
            "2026-04-19T20:20:00+09:00",
            "2026-04-19T20:20:01+09:00",
            "2026-04-19T20:20:02+09:00",
        ],
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: next(timestamps),
        ),
    )

    empty_response = client.get("/market/history")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "history": [],
    }

    for price in [820.0, 825.0, 830.0]:
        response = client.post(
            "/decision/entry",
            json={
                "prices": [800.0, 806.0, 813.0, price],
                "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
                "spread_bps": 8.0,
                "orderbook_imbalance": 0.24,
                "liquidity_score": 0.9,
                "regime_score": 0.78,
                "current_price": price,
                "slippage_bps": 10.0,
                "portfolio": {
                    "cash_balance": 500000.0,
                    "asset_currency": "XRP",
                    "asset_balance": 0.0,
                    "avg_buy_price": 0.0,
                },
                "safe_mode": False,
                "recent_loss_streak": 0,
            },
        )
        assert response.status_code == 200

    history_response = client.get("/market/history?limit=2")

    assert history_response.status_code == 200
    assert history_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "history": [
            {
                "market": "KRW-XRP",
                "price": 825.0,
                "recorded_at": "2026-04-19T20:20:01+09:00",
            },
            {
                "market": "KRW-XRP",
                "price": 830.0,
                "recorded_at": "2026-04-19T20:20:02+09:00",
            },
        ],
    }


def test_learning_recent_endpoint_returns_runtime_events(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:30:00+09:00",
        ),
    )

    response = client.get("/learning/recent")
    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "market": "KRW-XRP",
        "events": [],
    }

    execution_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execution_response.status_code == 200

    response = client.get("/learning/recent?limit=4")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["market"] == "KRW-XRP"
    assert [event["event_name"] for event in response.json()["events"]] == [
        "signal_generated",
        "fill_result",
        "position_opened",
    ]


def test_dashboard_market_endpoint_returns_market_summary(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    timestamps = iter(
        [
            "2026-04-19T20:40:00+09:00",
            "2026-04-19T20:40:01+09:00",
            "2026-04-19T20:40:02+09:00",
        ],
    )
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: next(timestamps),
        ),
    )

    for price in [820.0, 825.0, 830.0]:
        response = client.post(
            "/decision/entry",
            json={
                "prices": [800.0, 806.0, 813.0, price],
                "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
                "spread_bps": 8.0,
                "orderbook_imbalance": 0.24,
                "liquidity_score": 0.9,
                "regime_score": 0.78,
                "current_price": price,
                "slippage_bps": 10.0,
                "portfolio": {
                    "cash_balance": 500000.0,
                    "asset_currency": "XRP",
                    "asset_balance": 0.0,
                    "avg_buy_price": 0.0,
                },
                "safe_mode": False,
                "recent_loss_streak": 0,
            },
        )
        assert response.status_code == 200

    dashboard_response = client.get("/dashboard/market?history_limit=2")

    assert dashboard_response.status_code == 200
    assert dashboard_response.json() == {
        "status": "ok",
        "market": "KRW-XRP",
        "summary": {
            "market": "KRW-XRP",
            "state_label": "UP",
            "state_message": "최근 구간 기준 상승 흐름입니다.",
            "severity": "info",
            "current_price": 830.0,
            "recorded_at": "2026-04-19T20:40:02+09:00",
            "recent_change_pct": 0.0061,
            "history": [
                {
                    "market": "KRW-XRP",
                    "price": 825.0,
                    "recorded_at": "2026-04-19T20:40:01+09:00",
                },
                {
                    "market": "KRW-XRP",
                    "price": 830.0,
                    "recorded_at": "2026-04-19T20:40:02+09:00",
                },
            ],
        },
    }


def test_dashboard_learning_endpoint_returns_learning_summary(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:45:00+09:00",
        ),
    )

    empty_response = client.get("/dashboard/learning")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "learning": None,
    }

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    response = client.get("/dashboard/learning?limit=2")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["learning"]["total_events"] == 2
    assert response.json()["learning"]["severity"] == "info"
    assert response.json()["learning"]["state_message"] == "최근 학습 이벤트에 포지션 변화가 기록되었습니다."
    assert response.json()["learning"]["last_event_name"] == "position_opened"
    assert response.json()["learning"]["event_counts"] == {
        "fill_result": 1,
        "position_opened": 1,
    }
    assert [event["event_name"] for event in response.json()["learning"]["recent_events"]] == [
        "fill_result",
        "position_opened",
    ]


def test_dashboard_learning_health_endpoint_returns_category_summary(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            timestamp_provider=lambda: "2026-04-19T20:46:00+09:00",
        ),
    )

    empty_response = client.get("/dashboard/learning/health")
    assert empty_response.status_code == 200
    assert empty_response.json() == {
        "status": "empty",
        "health": None,
    }

    execute_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert execute_response.status_code == 200

    response = client.get("/dashboard/learning/health?limit=3")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["health"]["total_events"] == 3
    assert response.json()["health"]["severity"] == "info"
    assert response.json()["health"]["state_message"] == "최근 학습 상태가 정상적으로 기록되고 있습니다."
    assert response.json()["health"]["category_counts"] == {
        "signals": 1,
        "fills": 1,
        "positions": 1,
    }


def test_dashboard_recovery_endpoint_returns_recovery_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            from app.services.recovery.orchestrator import BootState

            return BootState(
                safe_mode=False,
                hard_stop=False,
                trading_ready=True,
                failure_stage=None,
                portfolio_state=None,
                reconcile_result=None,
            )

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")
    learning_service = LearningServiceStub()
    learning_service.record(
        LearningEvent(
            event_name="restart_detected",
            market="KRW-XRP",
            mode="demo",
            payload={"app_name": "test-app"},
            recorded_at="2026-04-20T10:00:00+09:00",
        ),
    )

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            learning_service=learning_service,
            timestamp_provider=lambda: "2026-04-20T10:00:00+09:00",
        ),
    )

    response = client.get("/dashboard/recovery")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["recovery"]["state_label"] == "OK"
    assert response.json()["recovery"]["state_message"] == "정상 복구가 완료되어 거래 가능 상태입니다."
    assert response.json()["recovery"]["recommended_action"] == "추가 조치 없이 운영을 지속할 수 있습니다."
    assert response.json()["recovery"]["severity"] == "info"
    assert response.json()["recovery"]["safe_mode"] is False
    assert response.json()["recovery"]["hard_stop"] is False
    assert response.json()["recovery"]["trading_ready"] is True
    assert response.json()["recovery"]["restart_count"] is None
    assert response.json()["recovery"]["blocked_reason"] is None
    assert response.json()["recovery"]["last_restart_detected_at"] == "2026-04-20T10:00:00+09:00"
    assert response.json()["recovery"]["hard_stop_triggered_at"] is None
    assert response.json()["recovery"]["recent_events"][0]["event_name"] == "restart_detected"
    assert response.json()["recovery"]["recent_recovery_timeline"] == [
        {
            "event_name": "restart_detected",
            "occurred_at": "2026-04-20T10:00:00+09:00",
            "severity": "warning",
            "app_name": "test-app",
            "trading_mode": None,
            "safe_mode": None,
            "trading_ready": None,
            "failure_stage": None,
            "open_order_count": None,
        },
    ]
    assert response.json()["recovery"]["recent_hard_stop_events"] == []
    assert response.json()["recovery"]["recent_hard_stop_timeline"] == []
    assert response.json()["recovery"]["recovery_timeline"] == [
        {
            "event_name": "restart_detected",
            "occurred_at": "2026-04-20T10:00:00+09:00",
            "severity": "warning",
            "app_name": "test-app",
            "trading_mode": None,
            "safe_mode": None,
            "trading_ready": None,
            "failure_stage": None,
            "open_order_count": None,
            "restart_count": None,
            "blocked_reason": None,
        },
    ]
    assert response.json()["recovery"]["current_state_summary"] == {
        "state_label": "OK",
        "state_message": "정상 복구가 완료되어 거래 가능 상태입니다.",
        "recommended_action": "추가 조치 없이 운영을 지속할 수 있습니다.",
        "severity": "info",
        "safe_mode": False,
        "hard_stop": False,
        "trading_ready": True,
        "failure_stage": None,
        "restart_count": None,
        "blocked_reason": None,
        "last_restart_detected_at": "2026-04-20T10:00:00+09:00",
        "last_recovery_completed_at": None,
        "hard_stop_triggered_at": None,
    }


def test_dashboard_executions_endpoint_returns_recent_fill_history(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    history_response = client.get("/dashboard/executions?limit=2")

    assert history_response.status_code == 200
    assert history_response.json()["status"] == "ok"
    assert len(history_response.json()["history"]) == 2
    assert history_response.json()["history"][0]["side"] == "buy"
    assert history_response.json()["history"][0]["severity"] == "info"
    assert history_response.json()["history"][0]["state_message"] == "매수 체결이 완료되었습니다."
    assert history_response.json()["history"][1]["side"] == "sell"
    assert history_response.json()["history"][1]["severity"] == "critical"
    assert history_response.json()["history"][1]["state_message"] == "손절 매도 체결이 완료되었습니다."
    assert history_response.json()["history"][1]["reason_code"] == "STOP_LOSS_PRICE_HIT"


def test_dashboard_positions_history_endpoint_returns_position_lifecycle(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
        ),
    )

    buy_response = client.post(
        "/decision/execute",
        json={
            "prices": [800.0, 806.0, 813.0, 820.0],
            "traded_values": [800000.0, 850000.0, 1200000.0, 2100000.0],
            "spread_bps": 8.0,
            "orderbook_imbalance": 0.24,
            "liquidity_score": 0.9,
            "regime_score": 0.78,
            "current_price": 820.0,
            "slippage_bps": 10.0,
            "portfolio": {
                "cash_balance": 500000.0,
                "asset_currency": "XRP",
                "asset_balance": 0.0,
                "avg_buy_price": 0.0,
            },
            "safe_mode": False,
            "recent_loss_streak": 0,
        },
    )
    assert buy_response.status_code == 200

    stop_loss_price = client.get("/position/current").json()["position"]["stop_loss_price"]
    exit_response = client.post(
        "/position/exit",
        json={
            "current_price": stop_loss_price - 0.24,
            "elapsed_sec": 181,
            "momentum_score": 0.41,
            "orderbook_imbalance": -0.12,
        },
    )
    assert exit_response.status_code == 200

    history_response = client.get("/dashboard/positions/history?limit=2")

    assert history_response.status_code == 200
    assert history_response.json()["status"] == "ok"
    assert len(history_response.json()["history"]) == 2
    assert history_response.json()["history"][0]["event_type"] == "opened"
    assert history_response.json()["history"][0]["severity"] == "info"
    assert history_response.json()["history"][0]["state_message"] == "포지션 진입이 완료되었습니다."
    assert history_response.json()["history"][1]["event_type"] == "closed"
    assert history_response.json()["history"][1]["severity"] == "critical"
    assert history_response.json()["history"][1]["state_message"] == "손절 조건 충족으로 포지션이 종료되었습니다."
    assert history_response.json()["history"][1]["reason_code"] == "STOP_LOSS_PRICE_HIT"


def test_startup_sync_failure_keeps_safe_mode(monkeypatch) -> None:
    class FailingBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = False
                trading_ready = False
                failure_stage = "portfolio_sync"

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=FailingBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "mode": "demo",
        "learning_enabled": True,
        "safe_mode": True,
        "hard_stop": False,
        "trading_ready": False,
        "failure_stage": "portfolio_sync",
    }


def test_health_endpoint_reports_hard_stop_state(monkeypatch) -> None:
    class HardStopBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = True
                trading_ready = False
                failure_stage = "hard_stop"

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=HardStopBootOrchestrator()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "mode": "live",
        "learning_enabled": True,
        "safe_mode": True,
        "hard_stop": True,
        "trading_ready": False,
        "failure_stage": "hard_stop",
    }


def test_create_app_dispatches_boot_notification_when_boot_enters_hard_stop(monkeypatch) -> None:
    class HardStopBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = True
                hard_stop = True
                trading_ready = False
                failure_stage = "hard_stop"
                portfolio_state = None
                reconcile_result = {
                    "restart_count": 3,
                    "blocked_reason": "RESTART_THRESHOLD_EXCEEDED",
                }

            return BootState()

    dispatcher = BootNotificationDispatcherStub()
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LEARNING_ENABLED", "true")
    monkeypatch.setenv("TRADE_MARKET", "KRW-XRP")

    create_app(
        recovery_orchestrator=HardStopBootOrchestrator(),
        boot_notification_dispatcher=dispatcher,
        timestamp_provider=lambda: "2026-04-18T12:30:00+09:00",
    )

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["app_name"] == "upbit-auto-trader"
    assert dispatcher.calls[0]["market"] == "KRW-XRP"
    assert dispatcher.calls[0]["triggered_at"] == "2026-04-18T12:30:00+09:00"
    assert dispatcher.calls[0]["cause"] == "process_restart"
    assert dispatcher.calls[0]["boot_state"].hard_stop is True
    assert dispatcher.calls[0]["boot_state"].failure_stage == "hard_stop"


def test_create_app_dispatches_boot_notification_when_boot_is_normal(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    dispatcher = BootNotificationDispatcherStub()
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    create_app(
        recovery_orchestrator=SuccessfulBootOrchestrator(),
        boot_notification_dispatcher=dispatcher,
        timestamp_provider=lambda: "2026-04-18T12:35:00+09:00",
    )

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["cause"] == "process_restart"
    assert dispatcher.calls[0]["boot_state"].hard_stop is False


def test_promotion_review_endpoint_returns_runner_result(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    runner = PromotionRunnerStub(
        PromotionRunResult(
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
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
        ),
    )

    response = client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "evaluation": {
            "status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
        },
        "approval_result": {
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
        },
    }
    assert len(runner.requests) == 1
    assert runner.requests[0].market == "KRW-XRP"
    assert runner.requests[0].approval_granted is True


def test_promotion_review_endpoint_records_learning_event(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    runner = PromotionRunnerStub(
        PromotionRunResult(
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
    learning_service = LearningServiceStub()
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
            learning_service=learning_service,
        ),
    )

    response = client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:30:00+09:00",
        },
    )

    assert response.status_code == 200
    assert len(learning_service.events) == 1
    assert learning_service.events[0].event_name == "promotion_review_completed"
    assert learning_service.events[0].market == "KRW-XRP"
    assert learning_service.events[0].mode == "demo"
    assert learning_service.events[0].payload == {
        "demo_days": 16,
        "total_trades": 132,
        "profit_factor": 1.31,
        "max_drawdown": 0.051,
        "stoploss_failures": 0,
        "approval_granted": True,
        "approved_by": "manual_review",
        "activated_at": "2026-04-19T10:30:00+09:00",
        "evaluation_status": "READY_FOR_REVIEW",
        "approved": False,
        "rejection_reasons": [],
        "live_enabled": True,
        "safe_mode_entry": True,
        "reason_code": None,
    }


def test_promotion_status_endpoint_returns_empty_before_review(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/promotion/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "snapshot": None,
    }


def test_promotion_history_endpoint_returns_empty_before_review(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "history": [],
    }


def test_promotion_review_endpoint_uses_default_runner_when_not_injected(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["evaluation"] == {
        "status": "READY_FOR_REVIEW",
        "approved": False,
        "rejection_reasons": [],
    }
    assert response.json()["approval_result"] == {
        "live_enabled": True,
        "safe_mode_entry": True,
        "reason_code": None,
    }


def test_promotion_status_endpoint_returns_last_review_result(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    runner = PromotionRunnerStub(
        PromotionRunResult(
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
    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(
        create_app(
            recovery_orchestrator=SuccessfulBootOrchestrator(),
            promotion_runner=runner,
        ),
    )

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:50:00+09:00",
        },
    )

    response = client.get("/promotion/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "snapshot": {
            "market": "KRW-XRP",
            "evaluation_status": "READY_FOR_REVIEW",
            "approved": False,
            "rejection_reasons": [],
            "live_enabled": True,
            "safe_mode_entry": True,
            "reason_code": None,
            "reviewed_at": "2026-04-18T13:50:00+09:00",
        },
    }


def test_promotion_history_endpoint_returns_accumulated_reviews(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
    )
    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T11:00:00+09:00",
        },
    )

    response = client.get("/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "evaluation_status": "NOT_READY",
                "approved": False,
                "rejection_reasons": [
                    "DEMO_DAYS_BELOW_THRESHOLD",
                    "TRADE_COUNT_BELOW_THRESHOLD",
                    "PROFIT_FACTOR_BELOW_THRESHOLD",
                    "MAX_DRAWDOWN_ABOVE_THRESHOLD",
                    "STOPLOSS_FAILURES_ABOVE_THRESHOLD",
                ],
                "live_enabled": False,
                "safe_mode_entry": False,
                "reason_code": "PROMOTION_NOT_READY",
                "reviewed_at": "2026-04-19T10:00:00+09:00",
            },
            {
                "market": "KRW-XRP",
                "evaluation_status": "READY_FOR_REVIEW",
                "approved": False,
                "rejection_reasons": [],
                "live_enabled": True,
                "safe_mode_entry": True,
                "reason_code": None,
                "reviewed_at": "2026-04-19T11:00:00+09:00",
            },
        ],
    }


def test_dashboard_summary_reflects_last_promotion_review_status(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    before_response = client.get("/dashboard/summary")

    assert before_response.status_code == 200
    assert before_response.json()["promotion_ready"] is False
    assert before_response.json()["section_severity"]["promotion"] == "warning"

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-18T13:55:00+09:00",
        },
    )

    after_response = client.get("/dashboard/summary")

    assert after_response.status_code == 200
    assert after_response.json()["promotion_ready"] is True
    assert after_response.json()["section_severity"]["promotion"] == "info"


def test_dashboard_promotion_returns_empty_before_review(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/dashboard/promotion")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "promotion": None,
    }


def test_dashboard_promotion_history_returns_empty_before_review(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    response = client.get("/dashboard/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "history": [],
    }


def test_dashboard_promotion_returns_last_review_payload(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
    )

    response = client.get("/dashboard/promotion")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "promotion": {
            "market": "KRW-XRP",
            "ready_for_review": False,
            "evaluation_status": "NOT_READY",
            "live_enabled": False,
            "safe_mode_entry": False,
            "reason_code": "PROMOTION_NOT_READY",
            "blocking_reasons": [
                "DEMO_DAYS_BELOW_THRESHOLD",
                "TRADE_COUNT_BELOW_THRESHOLD",
                "PROFIT_FACTOR_BELOW_THRESHOLD",
                "MAX_DRAWDOWN_ABOVE_THRESHOLD",
                "STOPLOSS_FAILURES_ABOVE_THRESHOLD",
            ],
            "reviewed_at": "2026-04-19T10:00:00+09:00",
        },
    }


def test_dashboard_promotion_history_returns_compact_review_timeline(monkeypatch) -> None:
    class SuccessfulBootOrchestrator:
        def boot(self):
            class BootState:
                safe_mode = False
                hard_stop = False
                trading_ready = True
                failure_stage = None
                portfolio_state = None
                reconcile_result = None

            return BootState()

    monkeypatch.setenv("TRADING_MODE", "demo")
    monkeypatch.setenv("LEARNING_ENABLED", "true")

    client = TestClient(create_app(recovery_orchestrator=SuccessfulBootOrchestrator()))

    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 7,
            "total_trades": 64,
            "profit_factor": 1.08,
            "max_drawdown": 0.11,
            "stoploss_failures": 2,
            "approval_granted": False,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T10:00:00+09:00",
        },
    )
    client.post(
        "/promotion/review",
        json={
            "market": "KRW-XRP",
            "demo_days": 16,
            "total_trades": 132,
            "profit_factor": 1.31,
            "max_drawdown": 0.051,
            "stoploss_failures": 0,
            "approval_granted": True,
            "approved_by": "manual_review",
            "activated_at": "2026-04-19T11:00:00+09:00",
        },
    )

    response = client.get("/dashboard/promotion/history")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "history": [
            {
                "market": "KRW-XRP",
                "reviewed_at": "2026-04-19T10:00:00+09:00",
                "evaluation_status": "NOT_READY",
                "ready_for_review": False,
                "live_enabled": False,
                "reason_code": "PROMOTION_NOT_READY",
            },
            {
                "market": "KRW-XRP",
                "reviewed_at": "2026-04-19T11:00:00+09:00",
                "evaluation_status": "READY_FOR_REVIEW",
                "ready_for_review": True,
                "live_enabled": True,
                "reason_code": None,
            },
        ],
    }
