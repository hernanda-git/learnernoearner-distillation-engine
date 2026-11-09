"""Module 3: 3-Tier Structural Geometry Engine (`proteus.geometry`).

Extracts the 72-hour horizontal range hierarchy (Range High, 50% Mid Range, Range Low),
liquidity sweeps past session extremes, and 'no-man's land' interior zones.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from proteus.domain.models import Candle, RangeGeometry
from proteus.market import normalize_base_symbol


class StructuralGeometryEngine:
    """Computes 3-tier horizontal range levels and confirmation events."""

    def __init__(
        self,
        level_proximity_pct: Decimal = Decimal("0.012"),
        wick_rejection_threshold: Decimal = Decimal("0.35"),
    ) -> None:
        self.level_proximity_pct = level_proximity_pct
        self.wick_rejection_threshold = wick_rejection_threshold

    def compute(
        self,
        symbol: str,
        candles_72h: Sequence[Candle],
        execution_candle: Candle | None = None,
    ) -> RangeGeometry:
        if not candles_72h:
            raise ValueError("candles_72h must contain at least one candle")

        base = normalize_base_symbol(symbol)
        current = execution_candle or candles_72h[-1]
        structural_pool = candles_72h[:-1] if len(candles_72h) > 1 and execution_candle is None else candles_72h

        range_high = max(c.high for c in structural_pool)
        range_low = min(c.low for c in structural_pool)
        mid_range = (range_high + range_low) / Decimal("2")

        if range_low > Decimal("0"):
            equilibrium_width_pct = ((range_high - range_low) / range_low) * Decimal("100")
        else:
            equilibrium_width_pct = Decimal("0")

        # Liquidity sweep of Range Low: wick pierces or touches Range Low and closes above
        low_tolerance = range_low * (Decimal("1") + self.level_proximity_pct * Decimal("0.5"))
        swept_low = (
            current.low <= low_tolerance
            and current.close > range_low
            and (current.lower_wick_ratio >= self.wick_rejection_threshold or current.is_bullish)
        )

        # Liquidity sweep / rejection at Range High: wick pierces or touches Range High and closes below
        high_tolerance = range_high * (Decimal("1") - self.level_proximity_pct * Decimal("0.5"))
        swept_high = (
            current.high >= high_tolerance
            and current.close < range_high
            and (current.upper_wick_ratio >= self.wick_rejection_threshold or not current.is_bullish)
        )

        # 50% Midrange retest from above (Long confirmation) or rejection from below (Short confirmation)
        mid_distance_pct = (
            abs(current.close - mid_range) / mid_range if mid_range > Decimal("0") else Decimal("1")
        )
        low_to_mid_pct = (
            abs(current.low - mid_range) / mid_range if mid_range > Decimal("0") else Decimal("1")
        )
        high_to_mid_pct = (
            abs(current.high - mid_range) / mid_range if mid_range > Decimal("0") else Decimal("1")
        )

        reclaimed_midrange = (
            current.close >= mid_range
            and (low_to_mid_pct <= self.level_proximity_pct or mid_distance_pct <= self.level_proximity_pct)
            and current.low <= mid_range * (Decimal("1") + self.level_proximity_pct)
        )

        rejected_midrange = (
            current.close < mid_range
            and (high_to_mid_pct <= self.level_proximity_pct or mid_distance_pct <= self.level_proximity_pct)
            and current.high >= mid_range * (Decimal("1") - self.level_proximity_pct)
        )

        # "No-man's land": price is floating between the 3 tiers without sweep or midrange confirmation
        near_low = (
            abs(current.close - range_low) / range_low <= self.level_proximity_pct
            if range_low > Decimal("0")
            else False
        )
        near_high = (
            abs(current.close - range_high) / range_high <= self.level_proximity_pct
            if range_high > Decimal("0")
            else False
        )
        near_mid = mid_distance_pct <= self.level_proximity_pct

        in_no_mans_land = not (
            swept_low
            or swept_high
            or reclaimed_midrange
            or rejected_midrange
            or near_low
            or near_high
            or near_mid
        )

        return RangeGeometry(
            symbol=base,
            range_high=range_high,
            range_low=range_low,
            mid_range=mid_range,
            equilibrium_width_pct=equilibrium_width_pct.quantize(Decimal("0.01")),
            swept_low=swept_low,
            swept_high=swept_high,
            reclaimed_midrange=reclaimed_midrange,
            rejected_midrange=rejected_midrange,
            in_no_mans_land=in_no_mans_land,
        )
