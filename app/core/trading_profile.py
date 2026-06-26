from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TradingProfileSpec:
    key: str
    label: str
    description: str
    auto_interval_sec: float
    auto_min_history: int
    min_net_edge_pct: float
    validation_window_sec: int
    min_expected_return_pct: float
    spread_bps: float
    slippage_bps: float
    fixed_stop_loss_pct: float

    def stop_loss_by_signal(self) -> dict[str, float]:
        return {
            "weak": self.fixed_stop_loss_pct,
            "medium": self.fixed_stop_loss_pct,
            "strong": self.fixed_stop_loss_pct,
            "very_strong": self.fixed_stop_loss_pct,
        }


TRADING_PROFILES: dict[str, TradingProfileSpec] = {
    "scalping": TradingProfileSpec(
        key="scalping",
        label="단타",
        description="짧은 주기로 관찰하고 수수료를 넘는 빠른 신호만 진입",
        auto_interval_sec=3.0,
        auto_min_history=6,
        min_net_edge_pct=0.0008,
        validation_window_sec=300,   # 완화: 3분 → 5분 (단기 휩소 방지)
        min_expected_return_pct=0.004,
        spread_bps=8.0,
        slippage_bps=12.0,
        fixed_stop_loss_pct=0.030,
    ),
    "short_term": TradingProfileSpec(
        key="short_term",
        label="단기",
        description="수분 단위 흐름을 더 확인하고 단타보다 높은 기대값을 요구",
        auto_interval_sec=10.0,
        auto_min_history=12,
        min_net_edge_pct=0.0020,
        validation_window_sec=900,
        min_expected_return_pct=0.008,
        spread_bps=10.0,
        slippage_bps=15.0,
        fixed_stop_loss_pct=0.030,
    ),
    "mid_term": TradingProfileSpec(
        key="mid_term",
        label="중기",
        description="추세 지속성과 리스크 여유를 더 크게 보고 진입",
        auto_interval_sec=30.0,
        auto_min_history=20,
        min_net_edge_pct=0.0060,
        validation_window_sec=3600,
        min_expected_return_pct=0.015,
        spread_bps=12.0,
        slippage_bps=18.0,
        fixed_stop_loss_pct=0.050,
    ),
    "long_term": TradingProfileSpec(
        key="long_term",
        label="장기",
        description="가장 느리게 관찰하고 높은 기대값과 장기 검증 창을 요구",
        auto_interval_sec=60.0,
        auto_min_history=30,
        min_net_edge_pct=0.0120,
        validation_window_sec=14400,
        min_expected_return_pct=0.030,
        spread_bps=15.0,
        slippage_bps=20.0,
        fixed_stop_loss_pct=0.100,
    ),
}


def get_trading_profile(key: str) -> TradingProfileSpec:
    try:
        return TRADING_PROFILES[key]
    except KeyError as exc:
        allowed = ", ".join(sorted(TRADING_PROFILES))
        raise ValueError(f"TRADING_PROFILE must be one of: {allowed}") from exc


def learning_log_dir_for_profile(base_dir: Path, profile: str) -> Path:
    return base_dir / profile


def learning_log_dir_for_coin_profile(base_dir: Path, profile: str, trade_coin: str) -> Path:
    coin = "".join(char for char in trade_coin.upper() if char.isalnum())
    if not coin or coin == "XRP":
        return learning_log_dir_for_profile(base_dir, profile)
    return base_dir / coin / profile
