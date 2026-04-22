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

    assert payload == {
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
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 300,
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": 300},
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
                    {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                    {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                    {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Stop Loss Count 0', "recommended_action": '손절 카운트를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": 0},
                    {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0.0},
                    {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "value": 0.0},
                    {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Recent Stop Loss Reason 기록 없음', "recommended_action": '손절 사유 발생 여부만 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS_REASON', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": None},
                ],
            },
            {
                "key": "learning",
                "name": "Learning",
                "state_label": "ACTIVE",
                "severity": "info",
                "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
                "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 300,
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 300},
                ],
                "metrics": {
                    "last_learning_event": None,
                    "learning_signal_count": 0,
                    "learning_fill_count": 0,
                    "last_signal_recorded_at": None,
                    "last_fill_recorded_at": None,
                },
                "metric_items": [
                    {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                    {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                    {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                ],
            },
            {
                "key": "recovery",
                "name": "Recovery",
                "state_label": "OK",
                "severity": "info",
                "state_message": "복구 상태가 정상입니다.",
                "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 600,
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": 600},
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
                    {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                    {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                    {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": True},
                    {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
                    {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
                ],
            },
            {
                "key": "promotion",
                "name": "Promotion",
                "state_label": "READY",
                "severity": "info",
                "state_message": "실거래 승격 검토 준비가 완료되었습니다.",
                "recommended_action": "승격 검토 또는 수동 승인 절차를 진행하세요.",
                "updated_at": "2026-04-19T18:00:00+09:00",
                "stale": False,
                "age_sec": 7200,
                "freshness_state": "fresh",
                "freshness_message": "최근 데이터",
                "freshness_label": "RECENT",
                "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
                "freshness_severity": "info",
                "freshness_window_sec": 86400,
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T18:00:00+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": "2026-04-19T18:00:00+09:00"},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 7200', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 7200},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 86400},
                ],
                "metrics": {
                    "promotion_ready": True,
                    "last_promotion_reviewed_at": "2026-04-19T18:00:00+09:00",
                },
                "metric_items": [
                    {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Promotion Ready 준비됨', "recommended_action": '승격 검토 또는 승인 절차를 진행하세요.', "recommended_action_label": 'PROCEED_PROMOTION', "action_group": 'proceed', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": True},
                    {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 2026-04-19T18:00:00+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": "2026-04-19T18:00:00+09:00"},
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
    }


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
    assert payload["sections"] == [
        {
            "key": "trading",
            "name": "Trading",
            "state_label": "STOP_LOSS_TRIGGERED",
                "severity": "critical",
                "state_message": "최근 손절 사유: STOP_LOSS_PRICE_HIT",
                "recommended_action": "최근 손절 발생 원인과 청산 흐름을 점검하세요.",
                "updated_at": None,
                "stale": True,
                "age_sec": None,
                "freshness_state": "missing",
                "freshness_message": "데이터 없음",
                "freshness_label": "MISSING",
                "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
                "freshness_severity": "warning",
                "freshness_window_sec": 300,
                "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": 300},
                ],
                "metrics": {
                "buy_count": 1,
                "sell_count": 1,
                "stop_loss_count": 1,
                "realized_pnl": payload["realized_pnl"],
                "unrealized_pnl": 0.0,
                "recent_stop_loss_reason": "STOP_LOSS_PRICE_HIT",
            },
            "metric_items": [
                {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 1', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 1},
                {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 1', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 1},
                {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "critical", "state_message": 'Stop Loss Count 1', "recommended_action": '최근 손절 흐름과 청산 원인을 점검하세요.', "recommended_action_label": 'REVIEW_STOP_LOSS', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": 1},
                {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "warning", "state_message": (f"Realized PnL 손실 {payload["realized_pnl"]}" if payload["realized_pnl"] < 0 else (f"Realized PnL 이익 {payload["realized_pnl"]}" if payload["realized_pnl"] > 0 else f"Realized PnL {payload["realized_pnl"]}")), "recommended_action": ('손익 악화 원인과 리스크 설정을 점검하세요.' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else '손익 흐름을 유지하며 모니터링하세요.'), "recommended_action_label": ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL'), "action_group": ('proceed' if 'PROCEED_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('check' if 'CHECK_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('review' if ('REVIEW_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') or 'IMPROVE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL')) else ('reference' if 'REFERENCE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('check' if 'CHECK_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('review' if ('REVIEW_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') or 'IMPROVE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL')) else ('reference' if 'REFERENCE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('check' if 'CHECK_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('review' if ('REVIEW_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') or 'IMPROVE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL')) else ('reference' if 'REFERENCE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('check' if 'CHECK_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else ('review' if ('REVIEW_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') or 'IMPROVE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL')) else ('reference' if 'REFERENCE_' in ('REVIEW_PNL' if isinstance(payload["realized_pnl"], (int, float)) and payload["realized_pnl"] < 0 else 'MONITOR_PNL') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": payload["realized_pnl"]},
                {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "value": 0.0},
                {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "critical", "state_message": 'Recent Stop Loss Reason STOP_LOSS_PRICE_HIT', "recommended_action": '최근 손절 사유를 검토하고 재진입 조건을 점검하세요.', "recommended_action_label": 'REVIEW_STOP_LOSS_REASON', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": "STOP_LOSS_PRICE_HIT"},
            ],
        },
        {
            "key": "learning",
            "name": "Learning",
            "state_label": "ACTIVE",
            "severity": "info",
            "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 300,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 300},
            ],
            "metrics": {
                "last_learning_event": None,
                "learning_signal_count": 0,
                "learning_fill_count": 0,
                "last_signal_recorded_at": None,
                "last_fill_recorded_at": None,
            },
            "metric_items": [
                {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
            ],
        },
        {
            "key": "recovery",
            "name": "Recovery",
            "state_label": "OK",
            "severity": "info",
            "state_message": "복구 상태가 정상입니다.",
            "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 600,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": 600},
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
                {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": True},
                {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
                {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
            ],
        },
        {
            "key": "promotion",
            "name": "Promotion",
            "state_label": "NOT_READY",
            "severity": "warning",
            "state_message": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
            "recommended_action": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 86400,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 86400},
            ],
            "metrics": {
                "promotion_ready": False,
                "last_promotion_reviewed_at": None,
            },
            "metric_items": [
                {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "warning", "state_message": 'Promotion Ready 미준비', "recommended_action": '승격 기준 미달 항목을 보완하세요.', "recommended_action_label": 'IMPROVE_PROMOTION', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": False},
                {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
            ],
        },
    ]
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
    assert payload["sections"] == [
        {
            "key": "trading",
            "name": "Trading",
            "state_label": "NORMAL",
            "severity": "info",
            "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.",
            "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요.",
            "updated_at": payload["last_fill_recorded_at"],
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 300,
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": None},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": 300},
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
                {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Stop Loss Count 0', "recommended_action": '손절 카운트를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": 0},
                {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0.0},
                {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 이익 2500.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "value": 2500.0},
                {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Recent Stop Loss Reason 기록 없음', "recommended_action": '손절 사유 발생 여부만 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS_REASON', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": None},
            ],
        },
        {
            "key": "learning",
            "name": "Learning",
            "state_label": "ACTIVE",
            "severity": "info",
            "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 300,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 300},
            ],
            "metrics": {
                "last_learning_event": None,
                "learning_signal_count": 0,
                "learning_fill_count": 0,
                "last_signal_recorded_at": None,
                "last_fill_recorded_at": None,
            },
            "metric_items": [
                {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 0},
                {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Signal At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
                {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Fill At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": None},
            ],
        },
        {
            "key": "recovery",
            "name": "Recovery",
            "state_label": "OK",
            "severity": "info",
            "state_message": "복구 상태가 정상입니다.",
            "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 600,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": 600},
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
                {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": True},
                {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Restart At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
                {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Recovery At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": None},
            ],
        },
        {
            "key": "promotion",
            "name": "Promotion",
            "state_label": "NOT_READY",
            "severity": "warning",
            "state_message": "실거래 승격 검토 준비가 아직 완료되지 않았습니다.",
            "recommended_action": "승격 기준 미달 지표를 보완한 뒤 다시 검토하세요.",
            "updated_at": None,
            "stale": True,
            "age_sec": None,
            "freshness_state": "missing",
            "freshness_message": "데이터 없음",
            "freshness_label": "MISSING",
            "freshness_recommended_action": "데이터 소스와 수집 경로를 확인하세요.",
            "freshness_severity": "warning",
            "freshness_window_sec": 86400,
            "freshness_metric_items": [
                    {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
                    {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 기록 없음', "recommended_action": '데이터 갱신 경로를 확인하세요.', "recommended_action_label": 'CHECK_DATA_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
                    {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 86400},
            ],
            "metrics": {
                "promotion_ready": False,
                "last_promotion_reviewed_at": None,
            },
            "metric_items": [
                {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "warning", "state_message": 'Promotion Ready 미준비', "recommended_action": '승격 기준 미달 항목을 보완하세요.', "recommended_action_label": 'IMPROVE_PROMOTION', "action_group": 'review', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": False},
                {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 기록 없음', "recommended_action": '해당 기록 경로를 확인하세요.', "recommended_action_label": 'CHECK_ACTIVITY_SOURCE', "action_group": 'check', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": None},
            ],
        },
    ]
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
    assert payload["sections"] == [
        {
            "key": "trading",
            "name": "Trading",
            "state_label": "NORMAL",
            "severity": "info",
            "state_message": "최근 체결 기준 거래 리스크 이상이 없습니다.",
            "recommended_action": "현재 거래 섹션은 모니터링만 유지하세요.",
            "updated_at": payload["last_fill_recorded_at"],
            "stale": False,
            "age_sec": 299,
            "freshness_state": "fresh",
            "freshness_message": "최근 데이터",
            "freshness_label": "RECENT",
            "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
            "freshness_severity": "info",
            "freshness_window_sec": 300,
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": f"Updated At {payload["last_fill_recorded_at"]}", "recommended_action": ('최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.' if payload["last_fill_recorded_at"] is not None else '데이터 갱신 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": payload["last_fill_recorded_at"]},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 299', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": 299},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.market", "action_tab_key": "overview", "value": 300},
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
                {"key": "buy_count", "label": "Buy Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Buy Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                {"key": "sell_count", "label": "Sell Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Sell Count 0', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0},
                {"key": "stop_loss_count", "label": "Stop Loss Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Stop Loss Count 0', "recommended_action": '손절 카운트를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": 0},
                {"key": "realized_pnl", "label": "Realized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Realized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.executions", "action_tab_key": "timeline", "value": 0.0},
                {"key": "unrealized_pnl", "label": "Unrealized PnL", "type": "pnl", "format_hint": "signed_currency", "severity": "info", "state_message": 'Unrealized PnL 0.0', "recommended_action": '손익 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_PNL', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.current", "action_tab_key": "current", "value": 0.0},
                {"key": "recent_stop_loss_reason", "label": "Recent Stop Loss Reason", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Recent Stop Loss Reason 기록 없음', "recommended_action": '손절 사유 발생 여부만 모니터링하세요.', "recommended_action_label": 'MONITOR_STOP_LOSS_REASON', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.positions.history", "action_tab_key": "history", "value": None},
            ],
        },
        {
            "key": "learning",
            "name": "Learning",
            "state_label": "ACTIVE",
            "severity": "info",
            "state_message": "학습 이벤트 기록이 활성화되어 있습니다.",
            "recommended_action": "학습 로그 적재가 유지되는지만 주기적으로 확인하세요.",
            "updated_at": payload["last_fill_recorded_at"],
            "stale": False,
            "age_sec": 299,
            "freshness_state": "fresh",
            "freshness_message": "최근 데이터",
            "freshness_label": "RECENT",
            "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
            "freshness_severity": "info",
            "freshness_window_sec": 300,
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": f"Updated At {payload["last_fill_recorded_at"]}", "recommended_action": ('최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.' if payload["last_fill_recorded_at"] is not None else '데이터 갱신 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_fill_recorded_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": payload["last_fill_recorded_at"]},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 299', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 299},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 300', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 300},
            ],
            "metrics": {
                "last_learning_event": "position_opened",
                "learning_signal_count": 1,
                "learning_fill_count": 1,
                "last_signal_recorded_at": payload["last_signal_recorded_at"],
                "last_fill_recorded_at": payload["last_fill_recorded_at"],
            },
            "metric_items": [
                {"key": "last_learning_event", "label": "Last Learning Event", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Last Learning Event position_opened', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": "position_opened"},
                {"key": "learning_signal_count", "label": "Signal Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Signal Count 1', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 1},
                {"key": "learning_fill_count", "label": "Fill Count", "type": "count", "format_hint": "integer", "severity": "info", "state_message": 'Fill Count 1', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": 1},
                {"key": "last_signal_recorded_at", "label": "Last Signal At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": f"Last Signal At {payload["last_signal_recorded_at"]}", "recommended_action": ('현재 기록 흐름을 유지하며 모니터링하세요.' if payload["last_signal_recorded_at"] is not None else '해당 기록 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_signal_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": payload["last_signal_recorded_at"]},
                {"key": "last_fill_recorded_at", "label": "Last Fill At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": f"Last Fill At {payload["last_fill_recorded_at"]}", "recommended_action": ('현재 기록 흐름을 유지하며 모니터링하세요.' if payload["last_fill_recorded_at"] is not None else '해당 기록 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_fill_recorded_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.learning", "action_tab_key": "recent-events", "value": payload["last_fill_recorded_at"]},
            ],
        },
        {
            "key": "recovery",
            "name": "Recovery",
            "state_label": "OK",
            "severity": "info",
            "state_message": "복구 상태가 정상입니다.",
            "recommended_action": "현재 복구 상태를 유지하며 다음 재시작 이벤트를 모니터링하세요.",
            "updated_at": payload["last_recovery_completed_at"],
            "stale": False,
            "age_sec": 296,
            "freshness_state": "fresh",
            "freshness_message": "최근 데이터",
            "freshness_label": "RECENT",
            "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
            "freshness_severity": "info",
            "freshness_window_sec": 600,
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": f"Updated At {payload["last_recovery_completed_at"]}", "recommended_action": ('최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.' if payload["last_recovery_completed_at"] is not None else '데이터 갱신 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') or 'IMPROVE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_FRESHNESS' if payload["last_recovery_completed_at"] is not None else 'CHECK_DATA_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": payload["last_recovery_completed_at"]},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 296', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": 296},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 600', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": 600},
            ],
            "metrics": {
                "safe_mode": False,
                "hard_stop": False,
                "trading_ready": True,
                "failure_stage": None,
                "last_restart_detected_at": payload["last_restart_detected_at"],
                "last_recovery_completed_at": payload["last_recovery_completed_at"],
            },
            "metric_items": [
                {"key": "safe_mode", "label": "Safe Mode", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Safe Mode 비활성', "recommended_action": '현재 복구 상태를 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_RECOVERY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "hard_stop", "label": "Hard Stop", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Hard Stop 비활성', "recommended_action": '하드스톱 조건 발생 여부를 계속 모니터링하세요.', "recommended_action_label": 'MONITOR_HARD_STOP', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": False},
                {"key": "trading_ready", "label": "Trading Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Trading Ready 준비됨', "recommended_action": '거래 준비 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_TRADING_READY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": True},
                {"key": "failure_stage", "label": "Failure Stage", "type": "text", "format_hint": "plain_text", "severity": "info", "state_message": 'Failure Stage 기록 없음', "recommended_action": '현재 실패 단계 없이 정상 상태를 유지하세요.', "recommended_action_label": 'MAINTAIN_NORMAL_STATE', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.recovery", "action_tab_key": "status", "value": None},
                {"key": "last_restart_detected_at", "label": "Last Restart At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": f"Last Restart At {payload["last_restart_detected_at"]}", "recommended_action": ('현재 기록 흐름을 유지하며 모니터링하세요.' if payload["last_restart_detected_at"] is not None else '해당 기록 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_restart_detected_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": payload["last_restart_detected_at"]},
                {"key": "last_recovery_completed_at", "label": "Last Recovery At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": f"Last Recovery At {payload["last_recovery_completed_at"]}", "recommended_action": ('현재 기록 흐름을 유지하며 모니터링하세요.' if payload["last_recovery_completed_at"] is not None else '해당 기록 경로를 확인하세요.'), "recommended_action_label": ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE'), "action_group": ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))), "action_priority": ('high' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ('proceed', 'review', 'check') else ('medium' if ('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) == 'reference' else 'low')), "actionable": (('proceed' if 'PROCEED_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('check' if 'CHECK_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else ('review' if ('REVIEW_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') or 'IMPROVE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE')) else ('reference' if 'REFERENCE_' in ('MONITOR_ACTIVITY' if payload["last_recovery_completed_at"] is not None else 'CHECK_ACTIVITY_SOURCE') else 'monitor')))) in ("proceed", "review", "check")), "action_url_key": "dashboard.recovery", "action_tab_key": "timeline", "value": payload["last_recovery_completed_at"]},
            ],
        },
        {
            "key": "promotion",
            "name": "Promotion",
            "state_label": "READY",
            "severity": "info",
            "state_message": "실거래 승격 검토 준비가 완료되었습니다.",
            "recommended_action": "승격 검토 또는 수동 승인 절차를 진행하세요.",
            "updated_at": "2026-04-19T20:00:03+09:00",
            "stale": False,
            "age_sec": 297,
            "freshness_state": "fresh",
            "freshness_message": "최근 데이터",
            "freshness_label": "RECENT",
            "freshness_recommended_action": "현재 갱신 상태를 유지하며 모니터링하세요.",
            "freshness_severity": "info",
            "freshness_window_sec": 86400,
            "freshness_metric_items": [
                {"key": "updated_at", "label": "Updated At", "type": "timestamp", "state_message": 'Updated At 2026-04-19T20:00:03+09:00', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": "2026-04-19T20:00:03+09:00"},
                {"key": "age_sec", "label": "Age Seconds", "type": "duration_sec", "state_message": 'Age Seconds 297', "recommended_action": '최근 갱신 시각을 기준으로 데이터 freshness를 모니터링하세요.', "recommended_action_label": 'MONITOR_FRESHNESS', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 297},
                {"key": "freshness_window_sec", "label": "Freshness Window Seconds", "type": "window_sec", "state_message": 'Freshness Window Seconds 86400', "recommended_action": 'freshness 기준 시간을 참고해 데이터 지연 여부를 판단하세요.', "recommended_action_label": 'REFERENCE_FRESHNESS_WINDOW', "action_group": 'reference', "action_priority": 'medium', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": 86400},
            ],
            "metrics": {
                "promotion_ready": True,
                "last_promotion_reviewed_at": "2026-04-19T20:00:03+09:00",
            },
            "metric_items": [
                {"key": "promotion_ready", "label": "Promotion Ready", "type": "boolean", "format_hint": "boolean_badge", "severity": "info", "state_message": 'Promotion Ready 준비됨', "recommended_action": '승격 검토 또는 승인 절차를 진행하세요.', "recommended_action_label": 'PROCEED_PROMOTION', "action_group": 'proceed', "action_priority": 'high', "actionable": True, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": True},
                {"key": "last_promotion_reviewed_at", "label": "Last Promotion Review At", "type": "timestamp", "format_hint": "datetime", "severity": "info", "state_message": 'Last Promotion Review At 2026-04-19T20:00:03+09:00', "recommended_action": '현재 기록 흐름을 유지하며 모니터링하세요.', "recommended_action_label": 'MONITOR_ACTIVITY', "action_group": 'monitor', "action_priority": 'low', "actionable": False, "action_url_key": "dashboard.promotion", "action_tab_key": "status", "value": "2026-04-19T20:00:03+09:00"},
            ],
        },
    ]
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
