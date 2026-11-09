"""Phase 6.3: Synthetic TradingView RGB Candlestick & Projection Box Renderer (`proteus.vision.renderer`).

Renders live multi-timeframe `Candle` series, 72h `RangeGeometry` S/R zones, and
candidate TP/SL projection boxes into an authentic 160x100 RGB TradingView canvas,
enabling `TradingViewBoxExtractor` to verify visual spatial IoU on live market bars.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from proteus.domain.models import BoundingBox, Candle, Direction, RangeGeometry
from proteus.vision.chart_extractor import ChartVisualExtraction, TradingViewBoxExtractor

# Canonical TradingView RGB palettes
DARK_BG = (19, 23, 34)
LIGHT_BG = (255, 255, 255)
TV_TEAL_PROFIT = (8, 153, 129)
TV_CRIMSON_STOP = (242, 54, 69)
TV_BLUE_SR_ZONE = (41, 98, 255)
TV_BULL_CANDLE = (90, 108, 120)
TV_BEAR_CANDLE = (120, 95, 105)


class SyntheticTradingViewRenderer:
    """Renders live candles and 3-tier geometry into a 160x100 RGB pixel matrix."""

    def __init__(self, width: int = 160, height: int = 100, dark_theme: bool = False) -> None:
        self.width = width
        self.height = height
        self.dark_theme = dark_theme
        self.extractor = TradingViewBoxExtractor()

    def render_and_extract_iou(
        self,
        candles: Sequence[Candle],
        geometry: RangeGeometry,
        direction: Direction,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> ChartVisualExtraction:
        if not candles:
            raise ValueError("candles must not be empty")

        bg_color = DARK_BG if self.dark_theme else LIGHT_BG
        grid: list[list[tuple[int, int, int]]] = [
            [bg_color for _ in range(self.width)] for _ in range(self.height)
        ]

        all_prices = [
            float(min(c.low for c in candles)),
            float(max(c.high for c in candles)),
            float(geometry.range_low),
            float(geometry.range_high),
            float(entry_price),
            float(stop_loss),
            float(take_profit),
        ]
        p_min = min(all_prices) * 0.995
        p_max = max(all_prices) * 1.005
        span = max(1e-12, p_max - p_min)

        def _price_to_row(p: float) -> int:
            norm_y = (p - p_min) / span
            clamped = max(0.0, min(1.0, norm_y))
            return int(round((1.0 - clamped) * (self.height - 1)))

        def _price_to_norm_y(p: float) -> float:
            return round(max(0.0, min(1.0, (p - p_min) / span)), 4)

        # 1. Paint horizontal S/R consolidation zone around 50% Midrange
        mid_f = float(geometry.mid_range)
        sr_top = _price_to_row(mid_f * 1.004)
        sr_bot = _price_to_row(mid_f * 0.996)
        for r in range(min(sr_top, sr_bot), max(sr_top, sr_bot) + 1):
            for c in range(10, self.width - 10):
                grid[r][c] = TV_BLUE_SR_ZONE

        # 2. Paint candlestick bodies across left 65% of canvas
        n_bars = min(len(candles), 32)
        recent = candles[-n_bars:]
        chart_right_col = int(self.width * 0.65)
        step_x = max(2, chart_right_col // max(1, n_bars))

        for idx, bar in enumerate(recent):
            col = min(chart_right_col - 1, 8 + idx * step_x)
            r_high = _price_to_row(float(bar.high))
            r_low = _price_to_row(float(bar.low))
            color = TV_BULL_CANDLE if bar.is_bullish else TV_BEAR_CANDLE
            for r in range(min(r_high, r_low), max(r_high, r_low) + 1):
                grid[r][col] = color

        # 3. Paint TradingView Long/Short Risk-Reward projection boxes on right 30% of canvas
        box_left = int(self.width * 0.66)
        box_right = int(self.width * 0.94)
        r_entry = _price_to_row(float(entry_price))
        r_tp = _price_to_row(float(take_profit))
        r_sl = _price_to_row(float(stop_loss))

        tp_r_min, tp_r_max = min(r_entry, r_tp), max(r_entry, r_tp)
        sl_r_min, sl_r_max = min(r_entry, r_sl), max(r_entry, r_sl)
        if tp_r_min == tp_r_max:
            tp_r_max = min(self.height - 1, tp_r_min + 2)
        if sl_r_min == sl_r_max:
            sl_r_max = min(self.height - 1, sl_r_min + 2)

        for r in range(tp_r_min, tp_r_max + 1):
            for c in range(box_left, box_right + 1):
                grid[r][c] = TV_TEAL_PROFIT

        for r in range(sl_r_min, sl_r_max + 1):
            for c in range(box_left, box_right + 1):
                grid[r][c] = TV_CRIMSON_STOP

        # Construct ground-truth geometric profit box in normalized coordinates
        gt_y1 = _price_to_norm_y(float(min(entry_price, take_profit)))
        gt_y2 = _price_to_norm_y(float(max(entry_price, take_profit)))
        human_gt = BoundingBox(
            x_min=round(box_left / float(self.width - 1), 4),
            y_min=gt_y1,
            x_max=round(box_right / float(self.width - 1), 4),
            y_max=max(gt_y1 + 0.02, gt_y2),
        )

        return self.extractor.extract_from_rgb_grid(grid, human_profit_box=human_gt)
