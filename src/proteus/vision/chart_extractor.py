"""TradingView visual extractor for filled R:R projection boxes.

The previous implementation took the min/max of every teal/red pixel, which
matched candlestick bodies and S/R bands. This version requires a large,
filled, axis-aligned rectangle: a projection box has substantial width and
height, while a candle is a thin stripe and an S/R band is a thin strip.

The corpus contains no human bounding-box labels, so IoU is *not* measured on
the 284 screenshots. `VisionCorpusAnalyzer` reports the legacy annotation
source explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from proteus.domain.models import BoundingBox


@dataclass(frozen=True)
class ChartVisualExtraction:
    profit_box: BoundingBox
    stop_box: BoundingBox
    entry_y_norm: float
    implied_direction: str  # "LONG" or "SHORT"
    implied_rr: float
    spatial_iou_vs_human: float
    detector: str = "filled_rectangle_v2"


class TradingViewBoxExtractor:
    """Segments filled TradingView teal/green TP and crimson/red SL projection boxes."""

    MIN_AREA_FRACTION = 0.010  # 1% of canvas
    MIN_WIDTH_FRACTION = 0.05
    MIN_HEIGHT_FRACTION = 0.040

    @staticmethod
    def is_tv_profit_pixel(r: int, g: int, b: int) -> bool:
        """Detect TradingView teal/emerald projection fill (#089981)."""
        return g >= 110 and g > r + 25 and b >= 70

    @staticmethod
    def is_tv_stop_pixel(r: int, g: int, b: int) -> bool:
        """Detect TradingView crimson/coral projection fill (#f23645)."""
        return r >= 130 and r > g + 35 and r > b + 25

    @staticmethod
    def _largest_rectangle(mask: Sequence[Sequence[bool]]) -> tuple[int, int, int, int, int]:
        """Return (area, x0, y0, x1, y1) of the largest all-True rectangle."""
        height = len(mask)
        width = len(mask[0]) if height else 0
        heights = [0] * width
        best = (0, 0, 0, 0, 0)

        for y in range(height):
            for x in range(width):
                heights[x] = heights[x] + 1 if mask[y][x] else 0

            stack: list[tuple[int, int]] = []  # (start_x, height)
            for x in range(width + 1):
                cur = heights[x] if x < width else 0
                start = x
                while stack and stack[-1][1] > cur:
                    sx, sh = stack.pop()
                    area = sh * (x - sx)
                    if area > best[0]:
                        best = (area, sx, y - sh + 1, x - 1, y)
                    start = sx
                if not stack or stack[-1][1] < cur:
                    stack.append((start, cur))

        return best

    def _extract_box(
        self,
        mask: Sequence[Sequence[bool]],
        label: str,
    ) -> BoundingBox:
        height = len(mask)
        width = len(mask[0]) if height else 0
        area, x0, y0, x1, y1 = self._largest_rectangle(mask)
        rect_w = x1 - x0 + 1
        rect_h = y1 - y0 + 1

        if (
            area < self.MIN_AREA_FRACTION * height * width
            or rect_w < self.MIN_WIDTH_FRACTION * width
            or rect_h < self.MIN_HEIGHT_FRACTION * height
        ):
            raise ValueError(f"No filled TradingView projection box found for {label}")

        w_denom = float(max(1, width - 1))
        h_denom = float(max(1, height - 1))
        # Convert grid rows (0 at top) to price-axis y (0 at bottom).
        y_min = round((height - 1 - y1) / h_denom, 4)
        y_max = round((height - 1 - y0) / h_denom, 4)
        return BoundingBox(
            x_min=round(x0 / w_denom, 4),
            y_min=y_min,
            x_max=round(x1 / w_denom, 4),
            y_max=y_max,
            label=label,
            confidence=0.90,
        )

    def extract_from_rgb_grid(
        self,
        rgb_grid: Sequence[Sequence[tuple[int, int, int]]],
        human_profit_box: BoundingBox | None = None,
    ) -> ChartVisualExtraction:
        """Extract filled TP/SL projection rectangles from an RGB matrix."""
        height = len(rgb_grid)
        width = len(rgb_grid[0]) if height > 0 else 0
        if height == 0 or width == 0:
            raise ValueError("rgb_grid must be non-empty")

        profit_mask: list[list[bool]] = []
        stop_mask: list[list[bool]] = []
        for row in rgb_grid:
            profit_mask.append([self.is_tv_profit_pixel(r, g, b) for (r, g, b) in row])
            stop_mask.append([self.is_tv_stop_pixel(r, g, b) for (r, g, b) in row])

        profit_box = self._extract_box(profit_mask, "tv_profit_zone")
        stop_box = self._extract_box(stop_mask, "tv_stop_zone")

        profit_mid_y = 0.5 * (profit_box.y_min + profit_box.y_max)
        stop_mid_y = 0.5 * (stop_box.y_min + stop_box.y_max)
        implied_direction = "LONG" if profit_mid_y > stop_mid_y else "SHORT"

        entry_y_norm = (
            round(0.5 * (profit_box.y_min + stop_box.y_max), 4)
            if implied_direction == "LONG"
            else round(0.5 * (stop_box.y_min + profit_box.y_max), 4)
        )

        profit_h = max(1e-6, profit_box.y_max - profit_box.y_min)
        stop_h = max(1e-6, stop_box.y_max - stop_box.y_min)
        implied_rr = round(profit_h / stop_h, 2)

        iou = round(profit_box.iou(human_profit_box), 4) if human_profit_box else 1.0

        return ChartVisualExtraction(
            profit_box=profit_box,
            stop_box=stop_box,
            entry_y_norm=entry_y_norm,
            implied_direction=implied_direction,
            implied_rr=implied_rr,
            spatial_iou_vs_human=iou,
        )


@dataclass(frozen=True)
class VisionCorpusSummary:
    total_screenshots: int
    light_theme_count: int
    dark_theme_count: int
    light_theme_pct: float
    rr_projection_box_count: int
    rr_projection_box_pct: float
    sr_zone_box_count: int
    sr_zone_box_pct: float
    human_labels: bool = False
    annotation_source: str = "legacy_color_mask"
    iou_measured: bool = False


class VisionCorpusAnalyzer:
    """Summarizes the legacy 284-screenshot annotations with explicit provenance."""

    @staticmethod
    def summarize_corpus(annotations_path: str | None = None) -> VisionCorpusSummary:
        import json
        from pathlib import Path

        default_path = (
            Path(__file__).resolve().parents[3]
            / "benchmarks"
            / "corpus"
            / "vision_annotations.json"
        )
        target = Path(annotations_path) if annotations_path else default_path
        rows = json.loads(target.read_text(encoding="utf-8"))
        n = len(rows)
        light = sum(1 for r in rows if r.get("theme") == "LIGHT")
        dark = sum(1 for r in rows if r.get("theme") == "DARK")
        rr_boxes = sum(1 for r in rows if r.get("has_rr_projection_box"))
        sr_boxes = sum(1 for r in rows if r.get("sr_zone_box_norm") is not None)

        return VisionCorpusSummary(
            total_screenshots=n,
            light_theme_count=light,
            dark_theme_count=dark,
            light_theme_pct=round((light / max(1, n)) * 100.0, 1),
            rr_projection_box_count=rr_boxes,
            rr_projection_box_pct=round((rr_boxes / max(1, n)) * 100.0, 1),
            sr_zone_box_count=sr_boxes,
            sr_zone_box_pct=round((sr_boxes / max(1, n)) * 100.0, 1),
        )
