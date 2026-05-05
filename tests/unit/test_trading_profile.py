from pathlib import Path

from app.core.trading_profile import learning_log_dir_for_coin_profile


def test_learning_log_dir_uses_legacy_profile_path_for_default_xrp() -> None:
    assert learning_log_dir_for_coin_profile(Path("logs/learning"), "scalping", "XRP") == Path(
        "logs/learning/scalping",
    )


def test_learning_log_dir_isolated_by_non_default_trade_coin() -> None:
    assert learning_log_dir_for_coin_profile(Path("logs/learning"), "scalping", "btc") == Path(
        "logs/learning/BTC/scalping",
    )
