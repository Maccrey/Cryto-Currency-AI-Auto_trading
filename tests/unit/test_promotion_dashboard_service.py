from __future__ import annotations

from app.services.dashboard.promotion import (
    DashboardPromotion,
    DashboardPromotionHistoryEntry,
    PromotionDashboardService,
)
from app.services.promotion.status import PromotionStatusSnapshot


def test_promotion_dashboard_service_builds_current_payload() -> None:
    service = PromotionDashboardService()
    snapshot = PromotionStatusSnapshot(
        market="KRW-XRP",
        evaluation_status="NOT_READY",
        approved=False,
        rejection_reasons=["PROFIT_FACTOR_BELOW_THRESHOLD"],
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="PROMOTION_NOT_READY",
        reviewed_at="2026-04-19T10:00:00+09:00",
    )

    result = service.build_current(snapshot)

    assert result == DashboardPromotion(
        market="KRW-XRP",
        ready_for_review=False,
        evaluation_status="NOT_READY",
        live_enabled=False,
        safe_mode_entry=False,
        reason_code="PROMOTION_NOT_READY",
        blocking_reasons=["PROFIT_FACTOR_BELOW_THRESHOLD"],
        reviewed_at="2026-04-19T10:00:00+09:00",
    )


def test_promotion_dashboard_service_builds_history_payload() -> None:
    service = PromotionDashboardService()
    entries = [
        PromotionStatusSnapshot(
            market="KRW-XRP",
            evaluation_status="NOT_READY",
            approved=False,
            rejection_reasons=["PROFIT_FACTOR_BELOW_THRESHOLD"],
            live_enabled=False,
            safe_mode_entry=False,
            reason_code="PROMOTION_NOT_READY",
            reviewed_at="2026-04-19T10:00:00+09:00",
        ),
        PromotionStatusSnapshot(
            market="KRW-XRP",
            evaluation_status="READY_FOR_REVIEW",
            approved=False,
            rejection_reasons=[],
            live_enabled=True,
            safe_mode_entry=True,
            reason_code=None,
            reviewed_at="2026-04-19T11:00:00+09:00",
        ),
    ]

    result = service.build_history(entries)

    assert result == [
        DashboardPromotionHistoryEntry(
            market="KRW-XRP",
            reviewed_at="2026-04-19T10:00:00+09:00",
            evaluation_status="NOT_READY",
            ready_for_review=False,
            live_enabled=False,
            reason_code="PROMOTION_NOT_READY",
        ),
        DashboardPromotionHistoryEntry(
            market="KRW-XRP",
            reviewed_at="2026-04-19T11:00:00+09:00",
            evaluation_status="READY_FOR_REVIEW",
            ready_for_review=True,
            live_enabled=True,
            reason_code=None,
        ),
    ]
