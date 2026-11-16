"""Daily panel loading for the alpha research engine (`proteus.alpha.panel`).

The research panel is a directory of per-symbol JSONL files produced by
``scripts/fetch_research_panel.py``. Each row is one 4H bar:

    {"ts": 1700000000000, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "v": 123.4}

This module aggregates those bars into UTC daily bars and exposes them through
``Panel`` so every signal is computed from completed days only. No dependency
on pandas/numpy: the engine is deliberately stdlib-only so the same code runs
on the workstation and on the VPS.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

DAY_MS = 86_400_000


@dataclass(frozen=True, slots=True)
class DailyBar:
    """One completed UTC day. ``ts`` is the midnight open time in milliseconds."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def quote_volume(self) -> float:
        return self.close * self.volume

    @property
    def day(self) -> date:
        return datetime.fromtimestamp(self.ts / 1000, tz=UTC).date()


@dataclass(slots=True)
class SymbolSeries:
    """Daily bars for one symbol, sorted by timestamp."""

    symbol: str
    bars: list[DailyBar]
    by_ts: dict[int, DailyBar] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.by_ts: dict[int, DailyBar] = {bar.ts: bar for bar in self.bars}

    @property
    def first_ts(self) -> int | None:
        return self.bars[0].ts if self.bars else None

    @property
    def last_ts(self) -> int | None:
        return self.bars[-1].ts if self.bars else None


def _floor_day(ts_ms: int) -> int:
    return (int(ts_ms) // DAY_MS) * DAY_MS


def aggregate_daily(rows: Iterable[dict[str, float]]) -> list[DailyBar]:
    """Aggregate 4H rows into completed UTC daily bars."""
    grouped: dict[int, list[tuple[int, float, float, float, float, float]]] = {}
    for row in rows:
        ts = int(row["ts"])
        grouped.setdefault(_floor_day(ts), []).append(
            (
                ts,
                float(row["o"]),
                float(row["h"]),
                float(row["l"]),
                float(row["c"]),
                float(row.get("v", 0.0)),
            )
        )
    bars: list[DailyBar] = []
    for day_ts in sorted(grouped):
        chunk = sorted(grouped[day_ts], key=lambda item: item[0])
        bars.append(
            DailyBar(
                ts=day_ts,
                open=chunk[0][1],
                high=max(item[2] for item in chunk),
                low=min(item[3] for item in chunk),
                close=chunk[-1][4],
                volume=sum(item[5] for item in chunk),
            )
        )
    return bars


def load_symbol(path: Path) -> SymbolSeries:
    rows: list[dict[str, float]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return SymbolSeries(symbol=path.stem, bars=aggregate_daily(rows))


@dataclass
class Panel:
    """Aligned view over every symbol series available for research."""

    series: dict[str, SymbolSeries]
    calendar: list[int]
    btc: SymbolSeries | None = None

    @classmethod
    def load(
        cls,
        directory: Path | str,
        *,
        btc_symbol: str = "BTCUSDT",
        drop_partial_last_day: bool = True,
    ) -> Panel:
        root = Path(directory)
        files = sorted(root.glob("*.jsonl"))
        if not files:
            raise FileNotFoundError(
                f"no JSONL symbol files under {root}; run scripts/fetch_research_panel.py"
            )
        series: dict[str, SymbolSeries] = {}
        for path in files:
            try:
                loaded = load_symbol(path)
            except (OSError, json.JSONDecodeError, ValueError):
                # A file being written by another process is skipped, never
                # allowed to abort the whole panel.
                continue
            if not loaded.bars:
                continue
            series[loaded.symbol] = loaded

        if drop_partial_last_day:
            # The newest day is still forming. Drop it so no signal sees a
            # partially formed daily close.
            newest_ts = max(item.last_ts or 0 for item in series.values())
            today_ts = _floor_day(int(datetime.now(UTC).timestamp() * 1000))
            if newest_ts >= today_ts:
                for item in series.values():
                    if item.bars and item.bars[-1].ts >= today_ts:
                        item.bars = item.bars[:-1]
                        item.by_ts.pop(today_ts, None)

        calendar = sorted({bar.ts for item in series.values() for bar in item.bars})
        btc = series.get(btc_symbol)
        return cls(series=series, calendar=calendar, btc=btc)

    def symbols_on(self, ts: int) -> list[str]:
        return [symbol for symbol, item in self.series.items() if ts in item.by_ts]

    def bar(self, symbol: str, ts: int) -> DailyBar | None:
        item = self.series.get(symbol)
        return item.by_ts.get(ts) if item else None

    def history_length(self, symbol: str, ts: int) -> int:
        item = self.series.get(symbol)
        if item is None:
            return 0
        # Bars are sorted; count completed bars at or before ``ts``.
        low, high = 0, len(item.bars)
        while low < high:
            mid = (low + high) // 2
            if item.bars[mid].ts <= ts:
                low = mid + 1
            else:
                high = mid
        return low

    def window(self, start: int | None = None, end: int | None = None) -> list[int]:
        return [
            ts
            for ts in self.calendar
            if (start is None or ts >= start) and (end is None or ts <= end)
        ]


def parse_day(value: str) -> int:
    """Parse ``YYYY-MM-DD`` (or an ISO timestamp) into a UTC midnight epoch ms."""
    text = value.strip()
    if len(text) == 10:
        stamp = datetime.fromisoformat(f"{text}T00:00:00+00:00")
    else:
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    return _floor_day(int(stamp.timestamp() * 1000))


def day_range(first: int, last: int) -> list[int]:
    return [
        _floor_day(first) + index * DAY_MS
        for index in range((_floor_day(last) - _floor_day(first)) // DAY_MS + 1)
    ]


def shift_days(ts: int, days: int) -> int:
    return _floor_day(ts) + days * DAY_MS


def iso_day(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=UTC).strftime("%Y-%m-%d")


def day_after(ts: int) -> int:
    return ts + DAY_MS


def trading_days_between(first: int, last: int) -> int:
    return max(1, (last - first) // DAY_MS)


__all__ = [
    "DAY_MS",
    "DailyBar",
    "Panel",
    "SymbolSeries",
    "aggregate_daily",
    "day_after",
    "day_range",
    "iso_day",
    "load_symbol",
    "parse_day",
    "shift_days",
    "trading_days_between",
]
