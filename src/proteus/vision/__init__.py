"""Module 4: Visual Saliency & Bounding-Box Agent (`proteus.vision`).

Predicts horizontal S/R bounding boxes in normalized chart coordinates and
evaluates spatial Intersection-over-Union (IoU >= 0.80 acceptance threshold).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from proteus.domain.models import BoundingBox, Candle, RangeGeometry


class VisualSaliencyAgent:
    """Synthesizes structural S/R bounding boxes and evaluates IoU parity."""

    ACCEPTANCE_IOU_THRESHOLD: float = 0.80

    def propose_support_resistance_boxes(
        self,
        candles: Sequence[Candle],
        geometry: RangeGeometry,
        band_half_height_pct: Decimal = Decimal("0.006"),
    ) -> dict[str, BoundingBox]:
        """Project 3-tier structural levels into normalized [0, 1] chart bounding boxes."""
        if not candles:
            raise ValueError("candles must not be empty")

        chart_low = float(min(c.low for c in candles))
        chart_high = float(max(c.high for c in candles))
        span = max(1e-9, chart_high - chart_low)

        def _make_box(level: Decimal, label: str) -> BoundingBox:
            lvl = float(level)
            half_band = lvl * float(band_half_height_pct)
            y_min = max(0.0, min(1.0, (lvl - half_band - chart_low) / span))
            y_max = max(0.0, min(1.0, (lvl + half_band - chart_low) / span))
            return BoundingBox(
                x_min=0.0,
                y_min=y_min,
                x_max=1.0,
                y_max=max(y_min + 0.01, y_max),
                label=label,
                confidence=0.92,
            )

        return {
            "range_high": _make_box(geometry.range_high, "range_high_supply"),
            "mid_range": _make_box(geometry.mid_range, "mid_range_pivot"),
            "range_low": _make_box(geometry.range_low, "range_low_demand"),
        }

    def evaluate_saliency_parity(
        self,
        predicted: BoundingBox,
        human_annotated: BoundingBox,
    ) -> tuple[float, bool]:
        """Compute spatial IoU and check Phase 2 acceptance threshold (IoU >= 0.80)."""
        score = predicted.iou(human_annotated)
        return round(score, 4), score >= self.ACCEPTANCE_IOU_THRESHOLD
