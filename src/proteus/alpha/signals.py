"""Per-symbol rolling statistics for the alpha engine (`proteus.alpha.signals`).

Everything is computed from completed daily bars and indexed by bar position.
A value at index ``i`` uses bars ``<= i`` only; the simulator executes the
resulting target at the next day's open, so there is no look-ahead.

The implementation is stdlib-only and O(N) per series: rolling sums are updated
incrementally instead of rescanning windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from proteus.alpha.panel import SymbolSeries


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


@dataclass(slots=True)
class SeriesStats:
    """Rolling arrays for one symbol, aligned to its daily bars."""

    symbol: str
    ts: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]
    vol: list[float | None] = field(default_factory=list)
    atr: list[float | None] = field(default_factory=list)
    sma: dict[int, list[float | None]] = field(default_factory=dict)
    mom: dict[int, list[float | None]] = field(default_factory=dict)
    dollar_volume: list[float] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.ts)

    def index_of(self, ts: int) -> int | None:
        # Bars are sorted; binary search keeps the simulator O(days log N).
        low, high = 0, len(self.ts)
        while low < high:
            mid = (low + high) // 2
            if self.ts[mid] < ts:
                low = mid + 1
            else:
                high = mid
        return low if low < len(self.ts) and self.ts[low] == ts else None


def _rolling_sum(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        if index >= window - 1:
            out[index] = running / window
    return out


def _rolling_std(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    running_sq = 0.0
    for index, value in enumerate(values):
        running += value
        running_sq += value * value
        if index >= window:
            old = values[index - window]
            running -= old
            running_sq -= old * old
        if index >= window - 1:
            mean = running / window
            variance = max(0.0, running_sq / window - mean * mean)
            out[index] = math.sqrt(variance)
    return out


def compute_stats(
    series: SymbolSeries,
    *,
    lookbacks: tuple[int, ...] = (7, 14, 30, 60, 90, 180),
    ma_windows: tuple[int, ...] = (20, 50, 100, 200),
    vol_window: int = 30,
    atr_window: int = 20,
    dv_window: int = 7,
) -> SeriesStats:
    bars = series.bars
    count = len(bars)
    stats = SeriesStats(
        symbol=series.symbol,
        ts=[bar.ts for bar in bars],
        open=[bar.open for bar in bars],
        high=[bar.high for bar in bars],
        low=[bar.low for bar in bars],
        close=[bar.close for bar in bars],
        volume=[bar.volume for bar in bars],
    )
    if count == 0:
        return stats

    log_returns: list[float] = [0.0] * count
    for index in range(1, count):
        previous = bars[index - 1].close
        log_returns[index] = (
            math.log(bars[index].close / previous) if previous > 0 and bars[index].close > 0 else 0.0
        )

    daily_vol = _rolling_std(log_returns, vol_window)
    stats.vol = [
        None if value is None else value * math.sqrt(365.0) for value in daily_vol
    ]

    true_ranges: list[float] = [0.0] * count
    for index, bar in enumerate(bars):
        previous_close = bars[index - 1].close if index else bar.close
        true_ranges[index] = max(
            bar.high - bar.low,
            abs(bar.high - previous_close),
            abs(bar.low - previous_close),
        )
    stats.atr = _rolling_sum(true_ranges, atr_window)

    for window in ma_windows:
        stats.sma[window] = _rolling_sum(stats.close, window)

    for horizon in lookbacks:
        values: list[float | None] = [None] * count
        for index in range(horizon, count):
            base = bars[index - horizon].close
            if base > 0:
                values[index] = bars[index].close / base - 1.0
        stats.mom[horizon] = values

    dollar = [bar.close * bar.volume for bar in bars]
    stats.dollar_volume = [
        value if value is not None else 0.0 for value in _rolling_sum(dollar, dv_window)
    ]
    return stats


def cross_sectional_z(values: dict[str, float]) -> dict[str, float]:
    """Population z-score across the eligible cross-section."""
    if not values:
        return {}
    mean = sum(values.values()) / len(values)
    variance = sum((value - mean) ** 2 for value in values.values()) / len(values)
    std = math.sqrt(variance)
    if std <= 1e-12:
        return {symbol: 0.0 for symbol in values}
    return {symbol: (value - mean) / std for symbol, value in values.items()}


__all__ = ["SeriesStats", "_mean", "compute_stats", "cross_sectional_z"]
