from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt


@dataclass(frozen=True)
class FeatureSnapshot:
    ret_1s: float
    ret_5s: float
    ret_30s: float
    volume_multiple: float
    traded_value_multiple: float
    spread_bps: float
    orderbook_imbalance: float
    short_volatility: float
    regime_score: float
    liquidity_score: float
    rsi_14: float = 50.0
    macd_histogram: float = 0.0
    bollinger_position: float = 0.5
    ma_trend: float = 0.0
    stochastic_k: float = 50.0
    price_position_20: float = 0.5
    drawdown_from_high_20: float = 0.0
    rebound_from_low_20: float = 0.0
    trend_efficiency_20: float = 0.0


class MarketFeatureCalculator:
    """Compute momentum and liquidity features from recent market observations."""

    def calculate(
        self,
        *,
        prices: list[float],
        traded_values: list[float],
        spread_bps: float,
        orderbook_imbalance: float,
        liquidity_score: float,
        regime_score: float,
    ) -> FeatureSnapshot:
        if len(prices) < 2:
            raise ValueError("At least two prices are required")
        if len(traded_values) < 2:
            raise ValueError("At least two traded_values are required")

        ret_1s = _return(prices[-2], prices[-1])
        # 기본 자동매매 주기가 3초이므로 최근 3개 관측치는 약 5~6초
        # 모멘텀을 나타낸다. 전체 관측 구간과 분리해 동일 수익률이
        # 단기·장기 점수에 이중 반영되는 것을 방지한다.
        ret_5s = _return(prices[-min(len(prices), 3)], prices[-1])
        ret_30s = _return(prices[0], prices[-1])
        comparison_window = traded_values[-3:-1] if len(traded_values) >= 3 else traded_values[:-1]
        volume_multiple = traded_values[-1] / (sum(comparison_window) / len(comparison_window))
        traded_value_multiple = volume_multiple
        short_volatility = _average_absolute_return(
            [_return(a, b) for a, b in zip(prices[:-1], prices[1:])],
        )
        rsi_14 = _rsi(prices, period=14)
        macd_histogram = _macd_histogram(prices)
        bollinger_position = _bollinger_position(prices, period=20)
        ma_trend = _moving_average_trend(prices, short_period=5, long_period=20)
        stochastic_k = _stochastic_k(prices, period=14)
        price_position_20 = _price_position(prices, period=20)
        drawdown_from_high_20 = _drawdown_from_high(prices, period=20)
        rebound_from_low_20 = _rebound_from_low(prices, period=20)
        trend_efficiency_20 = _trend_efficiency(prices, period=20)

        return FeatureSnapshot(
            ret_1s=ret_1s,
            ret_5s=ret_5s,
            ret_30s=ret_30s,
            volume_multiple=volume_multiple,
            traded_value_multiple=traded_value_multiple,
            spread_bps=spread_bps,
            orderbook_imbalance=orderbook_imbalance,
            short_volatility=short_volatility,
            regime_score=regime_score,
            liquidity_score=liquidity_score,
            rsi_14=rsi_14,
            macd_histogram=macd_histogram,
            bollinger_position=bollinger_position,
            ma_trend=ma_trend,
            stochastic_k=stochastic_k,
            price_position_20=price_position_20,
            drawdown_from_high_20=drawdown_from_high_20,
            rebound_from_low_20=rebound_from_low_20,
            trend_efficiency_20=trend_efficiency_20,
        )


def _return(start_price: float, end_price: float) -> float:
    return log(end_price / start_price)


def _average_absolute_return(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(abs(value) for value in values) / len(values)


def _rsi(prices: list[float], *, period: int) -> float:
    if len(prices) < 2:
        return 50.0
    changes = [b - a for a, b in zip(prices[:-1], prices[1:])][-period:]
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    if avg_loss <= 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _macd_histogram(prices: list[float]) -> float:
    if len(prices) < 2 or prices[-1] <= 0:
        return 0.0
    macd_line = _ema(prices, 12) - _ema(prices, 26)
    macd_values = []
    for index in range(2, len(prices) + 1):
        window = prices[:index]
        macd_values.append(_ema(window, 12) - _ema(window, 26))
    signal = _ema(macd_values, 9) if macd_values else 0.0
    return round((macd_line - signal) / prices[-1], 6)


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value * alpha) + (ema * (1 - alpha))
    return ema


def _bollinger_position(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    if len(window) < 2:
        return 0.5
    mean = sum(window) / len(window)
    variance = sum((price - mean) ** 2 for price in window) / len(window)
    band_width = sqrt(variance) * 2
    if band_width <= 0:
        return 0.5
    lower = mean - band_width
    upper = mean + band_width
    return round(max(min((prices[-1] - lower) / (upper - lower), 1.0), 0.0), 4)


def _moving_average_trend(prices: list[float], *, short_period: int, long_period: int) -> float:
    if len(prices) < 2 or prices[-1] <= 0:
        return 0.0
    short_window = prices[-short_period:]
    long_window = prices[-long_period:]
    short_ma = sum(short_window) / len(short_window)
    long_ma = sum(long_window) / len(long_window)
    return round(max(min((short_ma - long_ma) / prices[-1], 0.05), -0.05), 6)


def _stochastic_k(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    low = min(window)
    high = max(window)
    if high <= low:
        return 50.0
    return round(((prices[-1] - low) / (high - low)) * 100, 2)


def _price_position(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    low = min(window)
    high = max(window)
    if high <= low:
        return 0.5
    return round(max(min((prices[-1] - low) / (high - low), 1.0), 0.0), 4)


def _drawdown_from_high(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    high = max(window)
    if high <= 0:
        return 0.0
    return round(min((prices[-1] - high) / high, 0.0), 6)


def _rebound_from_low(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    low = min(window)
    if low <= 0:
        return 0.0
    return round(max((prices[-1] - low) / low, 0.0), 6)


def _trend_efficiency(prices: list[float], *, period: int) -> float:
    window = prices[-period:]
    if len(window) < 2 or window[0] <= 0:
        return 0.0
    path = sum(abs(_return(a, b)) for a, b in zip(window[:-1], window[1:]))
    if path <= 0:
        return 0.0
    direct = _return(window[0], window[-1])
    return round(max(min(direct / path, 1.0), -1.0), 6)
