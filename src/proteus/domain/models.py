"""Domain models and immutable value objects for Project Proteus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class Action(str, Enum):
    ABSTAIN = "ABSTAIN"
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"


class OrderMode(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class MacroRegime(str, Enum):
    BULLISH_EXPANSION = "BULLISH_EXPANSION"
    RANGE_BOUND = "RANGE_BOUND"
    BREAKDOWN = "BREAKDOWN"


class SetupArchetype(str, Enum):
    MIDRANGE_RETEST = "MIDRANGE_RETEST"
    LIQUIDITY_SWEEP_RECLAIM = "LIQUIDITY_SWEEP_RECLAIM"
    RANGE_HIGH_REJECTION = "RANGE_HIGH_REJECTION"
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    NONE = "NONE"


class TradeState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BREAKEVEN_PROTECTED = "BREAKEVEN_PROTECTED"
    PARTIAL_TP_BOOKED = "PARTIAL_TP_BOOKED"
    BEDTIME_DERISKED = "BEDTIME_DERISKED"
    CLOSED_TP = "CLOSED_TP"
    CLOSED_SL = "CLOSED_SL"
    CLOSED_EARLY = "CLOSED_EARLY"


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def lower_wick_ratio(self) -> Decimal:
        total_range = self.high - self.low
        if total_range <= Decimal("0"):
            return Decimal("0")
        body_low = min(self.open, self.close)
        return (body_low - self.low) / total_range

    @property
    def upper_wick_ratio(self) -> Decimal:
        total_range = self.high - self.low
        if total_range <= Decimal("0"):
            return Decimal("0")
        body_high = max(self.open, self.close)
        return (self.high - body_high) / total_range


@dataclass(frozen=True)
class RangeGeometry:
    symbol: str
    range_high: Decimal
    range_low: Decimal
    mid_range: Decimal
    equilibrium_width_pct: Decimal
    swept_low: bool
    swept_high: bool
    reclaimed_midrange: bool
    rejected_midrange: bool
    in_no_mans_land: bool


@dataclass(frozen=True)
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    label: str = "consolidation_zone"
    confidence: float = 1.0

    def area(self) -> float:
        width = max(0.0, self.x_max - self.x_min)
        height = max(0.0, self.y_max - self.y_min)
        return width * height

    def iou(self, other: BoundingBox) -> float:
        inter_x_min = max(self.x_min, other.x_min)
        inter_y_min = max(self.y_min, other.y_min)
        inter_x_max = min(self.x_max, other.x_max)
        inter_y_max = min(self.y_max, other.y_max)

        inter_w = max(0.0, inter_x_max - inter_x_min)
        inter_h = max(0.0, inter_y_max - inter_y_min)
        inter_area = inter_w * inter_h
        if inter_area <= 0.0:
            return 0.0

        union_area = self.area() + other.area() - inter_area
        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area


@dataclass(frozen=True)
class PolicyDecision:
    action: Action
    direction: Optional[Direction]
    confidence: float
    abstain_prob: float
    archetype: SetupArchetype
    order_mode: Optional[OrderMode]
    rationale: str


@dataclass(frozen=True)
class TradeSetup:
    symbol: str
    direction: Direction
    order_mode: OrderMode
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    planned_rr: Decimal
    risk_pct: Decimal
    confidence: float
    archetype: SetupArchetype
    limit_band_low: Optional[Decimal] = None
    limit_band_high: Optional[Decimal] = None
    scale_factor: int = 1


@dataclass(frozen=True)
class PositionState:
    setup: TradeSetup
    state: TradeState
    current_sl: Decimal
    current_tp: Decimal
    remaining_size_fraction: Decimal
    realized_r: Decimal
    unrealized_r: Decimal
    opened_at_utc: datetime
    updated_at_utc: datetime
