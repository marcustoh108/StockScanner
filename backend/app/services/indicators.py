"""Technical indicators: EMA, ATR, support/resistance."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> float | None:
    if len(series) < span:
        return None
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])


def ema_series(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_emas(history: pd.DataFrame) -> dict:
    close = history["Close"]
    return {
        "ema9": ema(close, 9),
        "ema20": ema(close, 20),
        "ema50": ema(close, 50),
        "ema200": ema(close, 200),
    }


def atr(history: pd.DataFrame, period: int = 14) -> float | None:
    if len(history) < period + 1:
        return None
    high, low, close = history["High"], history["Low"], history["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def support_resistance(history: pd.DataFrame, lookback: int = 120, window: int = 5) -> dict:
    """Detect swing highs/lows via local-extrema pivots, cluster, and return the
    nearest support/resistance levels relative to the current price."""
    recent = history.tail(lookback)
    highs = recent["High"].to_numpy()
    lows = recent["Low"].to_numpy()
    n = len(recent)
    spot = float(recent["Close"].iloc[-1])

    pivot_highs: list[float] = []
    pivot_lows: list[float] = []
    for i in range(window, n - window):
        h_slice = highs[i - window : i + window + 1]
        l_slice = lows[i - window : i + window + 1]
        if highs[i] == h_slice.max():
            pivot_highs.append(float(highs[i]))
        if lows[i] == l_slice.min():
            pivot_lows.append(float(lows[i]))

    def cluster(levels: list[float], tolerance_pct: float = 0.01) -> list[float]:
        if not levels:
            return []
        levels = sorted(levels)
        clusters: list[list[float]] = [[levels[0]]]
        for lvl in levels[1:]:
            if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
                clusters[-1].append(lvl)
            else:
                clusters.append([lvl])
        return [float(np.mean(c)) for c in clusters]

    resistance_levels = sorted(l for l in cluster(pivot_highs) if l > spot)
    support_levels = sorted((l for l in cluster(pivot_lows) if l < spot), reverse=True)

    return {
        "spot": spot,
        "resistance": resistance_levels[:3],
        "support": support_levels[:3],
        "nearest_resistance": resistance_levels[0] if resistance_levels else None,
        "nearest_support": support_levels[0] if support_levels else None,
    }


def realized_volatility(history: pd.DataFrame, window: int = 20) -> pd.Series:
    """Annualized close-to-close realized volatility, rolling `window`-day."""
    log_ret = np.log(history["Close"] / history["Close"].shift(1))
    return log_ret.rolling(window).std() * np.sqrt(252)


def realized_volatility_latest(history: pd.DataFrame, window: int = 20) -> float | None:
    rv = realized_volatility(history, window)
    if rv.empty or pd.isna(rv.iloc[-1]):
        return None
    return float(rv.iloc[-1])
