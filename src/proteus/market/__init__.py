"""Module 1: Multi-Timeframe Market State & Air-Gapped Lakehouse (`proteus.market`)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable, Sequence

from proteus.domain.models import Candle

TRADABLE_UNIVERSE: tuple[str, ...] = (
    "WLD",
    "PUMP",
    "ENA",
    "ZEC",
    "PENGU",
    "INJ",
    "MAGIC",
    "NEAR",
    "GRASS",
    "PEPE",
    "SNDK",
    "TRUMP",
)

MACRO_COMPASS_ASSETS: tuple[str, ...] = ("BTC", "ETH")


def normalize_base_symbol(symbol: str) -> str:
    """Strip quote currency and perpetual suffixes to canonical ticker."""
    cleaned = symbol.upper().strip().lstrip("$")
    for suffix in ("/USDT:USDT", "/USDT", "-USDT-SWAP", "USDT", "PERP"):
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if cleaned.startswith("1000") and len(cleaned) > 4:
        cleaned = cleaned[4:]
    return cleaned


class MultiTimeframeStore:
    """In-memory multi-timeframe candle lakehouse for replay and negative space mining."""

    def __init__(self) -> None:
        self._candles: dict[tuple[str, str], list[Candle]] = defaultdict(list)

    def ingest(self, candles: Iterable[Candle]) -> int:
        count = 0
        affected_keys: set[tuple[str, str]] = set()
        for candle in candles:
            base = normalize_base_symbol(candle.symbol)
            key = (base, candle.timeframe)
            self._candles[key].append(candle)
            affected_keys.add(key)
            count += 1
        for key in affected_keys:
            self._candles[key].sort(key=lambda c: c.timestamp_utc)
        return count

    def get_window(
        self,
        symbol: str,
        timeframe: str,
        end_utc: datetime,
        lookback: timedelta,
    ) -> list[Candle]:
        base = normalize_base_symbol(symbol)
        start_utc = end_utc - lookback
        series = self._candles.get((base, timeframe), [])
        return [c for c in series if start_utc <= c.timestamp_utc <= end_utc]

    def get_signal_alignment_slice(
        self,
        symbol: str,
        timeframe: str,
        signal_time_utc: datetime,
        pre_days: int = 30,
        post_hours: int = 48,
    ) -> list[Candle]:
        """Extract [T0 - 30d, T0 + 48h] historical alignment window around a signal."""
        base = normalize_base_symbol(symbol)
        start_utc = signal_time_utc - timedelta(days=pre_days)
        end_utc = signal_time_utc + timedelta(hours=post_hours)
        series = self._candles.get((base, timeframe), [])
        return [c for c in series if start_utc <= c.timestamp_utc <= end_utc]

    def sample_negative_space(
        self,
        symbol: str,
        timeframe: str,
        signal_timestamps_utc: Sequence[datetime],
        exclusion_radius: timedelta = timedelta(hours=2),
        limit: int = 5000,
    ) -> list[Candle]:
        """Sample bars where the human trader actively abstained outside exclusion_radius."""
        base = normalize_base_symbol(symbol)
        series = self._candles.get((base, timeframe), [])
        negatives: list[Candle] = []
        for candle in series:
            if any(
                abs((candle.timestamp_utc - sig_ts).total_seconds())
                <= exclusion_radius.total_seconds()
                for sig_ts in signal_timestamps_utc
            ):
                continue
            negatives.append(candle)
            if len(negatives) >= limit:
                break
        return negatives

    @staticmethod
    def is_tradable_symbol(symbol: str) -> bool:
        base = normalize_base_symbol(symbol)
        if base in MACRO_COMPASS_ASSETS:
            return False
        return base in TRADABLE_UNIVERSE
