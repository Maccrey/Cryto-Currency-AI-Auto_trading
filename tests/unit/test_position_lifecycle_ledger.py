from app.services.position.ledger import PositionLifecycleLedger
from app.services.risk.stop_loss import PositionSnapshot


def test_position_lifecycle_ledger_records_recent_events() -> None:
    timestamps = iter(
        [
            "2026-04-19T21:00:00+09:00",
            "2026-04-19T21:00:01+09:00",
        ],
    )
    ledger = PositionLifecycleLedger(
        timestamp_provider=lambda: next(timestamps),
    )
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=100.0,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    opened = ledger.record(event_type="opened", position=position)
    reduced = ledger.record(
        event_type="reduced",
        position=PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=50.0,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
        reason_code="STOP_LOSS_MOMENTUM_REVERSAL",
    )

    assert opened.recorded_at == "2026-04-19T21:00:00+09:00"
    assert reduced.recorded_at == "2026-04-19T21:00:01+09:00"
    assert [record.event_type for record in ledger.list_records(limit=2)] == [
        "opened",
        "reduced",
    ]
