from app.services.position.store import CurrentPositionStore
from app.services.risk.stop_loss import PositionSnapshot


def test_current_position_store_saves_and_returns_position() -> None:
    store = CurrentPositionStore()
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    store.save(position)

    assert store.get() == position
    assert store.to_payload(position)["market"] == "KRW-XRP"


def test_current_position_store_clears_position() -> None:
    store = CurrentPositionStore()
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=190.5,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )

    store.clear()

    assert store.get() is None


def test_current_position_store_persists_position(tmp_path) -> None:
    storage_path = tmp_path / "current-position.json"
    position = PositionSnapshot(
        market="KRW-XRP",
        signal_level="strong",
        entry_price=820.0,
        quantity=190.5,
        stop_loss_price=805.24,
        stop_loss_pct=0.018,
        validation_window_sec=180,
        min_expected_return_pct=0.004,
        stop_loss_reason=None,
    )

    CurrentPositionStore(storage_path=storage_path).save(position)
    restored = CurrentPositionStore(storage_path=storage_path)

    assert restored.get() == position


def test_current_position_store_clear_persists_empty_state(tmp_path) -> None:
    storage_path = tmp_path / "current-position.json"
    store = CurrentPositionStore(storage_path=storage_path)
    store.save(
        PositionSnapshot(
            market="KRW-XRP",
            signal_level="strong",
            entry_price=820.0,
            quantity=190.5,
            stop_loss_price=805.24,
            stop_loss_pct=0.018,
            validation_window_sec=180,
            min_expected_return_pct=0.004,
            stop_loss_reason=None,
        ),
    )
    store.clear()

    restored = CurrentPositionStore(storage_path=storage_path)

    assert restored.get() is None
