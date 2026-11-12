"""Multi-Scale Fractal Horizontal Structure Engine (`proteus.geometry.fractal`).

Replaces the naive 72h rolling min/max box (which only recalled 25.3% of real setups)
with `@learnernoearner`'s actual 5-layer structural perception hierarchy computed
strictly on pre-entry candles (< T0, zero lookahead):
  1. 72h Wick & Candle-Body Range Tiers (Low, 50% Mid, High)
  2. 24h Daily Range Wick & Candle-Body Tiers (Low, 50% Mid, High)
  3. Multi-Touch Candle-Body Horizontal Clusters (>= 4 body opens/closes within 0.6%)
  4. 5-Bar Fractal Swing High/Low Pivots & Break-and-Retest (S/R Flip) Shelves
  5. Impulse Order Blocks (origin candle preceding a >= 1.8x ATR body expansion bar)
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_RAW_CANDLES_PATH = (
    Path(__file__).resolve().parents[3]
    / "benchmarks"
    / "corpus"
    / "real_1h_candles_by_signal.json"
)


@dataclass(frozen=True)
class FractalStructuralAnalysis:
    symbol: str
    matched_mechanism: str  # "72H_WICK_OR_BODY_TIER", "24H_DAILY_RANGE_TIER", "MULTI_TOUCH_BODY_CLUSTER", "FRACTAL_SWING_SR_FLIP", "IMPULSE_ORDER_BLOCK", "UNMATCHED_NO_MANS_LAND"
    recalled_by_fractal: bool
    recalled_by_naive_72h: bool
    nearest_level_price: float
    nearest_level_dist_pct: float
    pos_in_72h_range_pct: float
    pos_in_24h_range_pct: float
    expansion_24_72_ratio: float
    ret_24h_pct: float
    bounce_from_24h_lo_pct: float
    rvol_current: float
    broke_above_6h_high: bool
    lower_demand_reentry_level: float


@dataclass(frozen=True)
class BlindRecallComparisonReport:
    evaluated_real_series: int
    naive_72h_recalled_count: int
    naive_72h_recall_pct: float
    naive_72h_false_reject_pct: float
    fractal_recalled_count: int
    fractal_recall_pct: float
    mechanism_breakdown: dict[str, int]
    long_mean_24h_ret_pct: float
    short_mean_24h_ret_pct: float
    long_mean_bounce_from_low_pct: float
    short_mean_bounce_from_low_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FractalHorizontalStructureEngine:
    """Extracts multi-scale horizontal levels and evaluates zero-lookahead structural confluence."""

    def __init__(self, touch_tolerance_pct: float = 0.009) -> None:
        self.touch_tolerance_pct = touch_tolerance_pct

    @staticmethod
    def extract_levels_zero_lookahead(
        pre_candles: Sequence[Sequence[float]],
    ) -> dict[str, list[float]]:
        """Extract all 5 structural level families strictly from bars prior to T0 (`pre_candles[:-1]`)."""
        hist = list(pre_candles[:-1]) if len(pre_candles) > 4 else list(pre_candles)
        n = len(hist)
        if n == 0:
            raise ValueError("pre_candles must not be empty")

        w72_hi = max(float(r[2]) for r in hist)
        w72_lo = min(float(r[3]) for r in hist)
        w72_mid = 0.5 * (w72_hi + w72_lo)

        b72_hi = max(max(float(r[1]), float(r[4])) for r in hist)
        b72_lo = min(min(float(r[1]), float(r[4])) for r in hist)
        b72_mid = 0.5 * (b72_hi + b72_lo)

        rec24 = hist[-24:] if n >= 24 else hist
        w24_hi = max(float(r[2]) for r in rec24)
        w24_lo = min(float(r[3]) for r in rec24)
        w24_mid = 0.5 * (w24_hi + w24_lo)
        b24_hi = max(max(float(r[1]), float(r[4])) for r in rec24)
        b24_lo = min(min(float(r[1]), float(r[4])) for r in rec24)

        # 5-bar Fractal Swing Highs & Lows
        swing_pivots: list[float] = []
        for i in range(2, n - 2):
            hi_i = float(hist[i][2])
            lo_i = float(hist[i][3])
            if hi_i >= max(
                float(hist[i - 2][2]),
                float(hist[i - 1][2]),
                float(hist[i + 1][2]),
                float(hist[i + 2][2]),
            ):
                swing_pivots.append(hi_i)
            if lo_i <= min(
                float(hist[i - 2][3]),
                float(hist[i - 1][3]),
                float(hist[i + 1][3]),
                float(hist[i + 2][3]),
            ):
                swing_pivots.append(lo_i)

        # Multi-Touch Candle-Body Horizontal Clusters (>= 4 body tops/bottoms within 0.6%)
        body_pivots: list[float] = []
        for r in hist:
            body_pivots.append(max(float(r[1]), float(r[4])))
            body_pivots.append(min(float(r[1]), float(r[4])))

        body_clusters: list[float] = []
        for p in body_pivots:
            touches = sum(1 for q in body_pivots if abs(p - q) / max(1e-12, p) <= 0.006)
            if touches >= 4 and not any(
                abs(p - c) / max(1e-12, c) <= 0.006 for c in body_clusters
            ):
                body_clusters.append(p)

        # Impulse Order Blocks (origin candle before a >= 1.8x average-range body expansion)
        avg_range = sum(float(r[2]) - float(r[3]) for r in hist) / max(1, n)
        order_blocks: list[float] = []
        for i in range(1, n):
            bar_range = float(hist[i][2]) - float(hist[i][3])
            body_size = abs(float(hist[i][4]) - float(hist[i][1]))
            if bar_range >= 1.8 * avg_range and body_size >= 0.6 * bar_range:
                order_blocks.append(max(float(hist[i - 1][1]), float(hist[i - 1][4])))
                order_blocks.append(min(float(hist[i - 1][1]), float(hist[i - 1][4])))

        return {
            "72H_WICK_OR_BODY_TIER": [w72_lo, w72_mid, w72_hi, b72_lo, b72_mid, b72_hi],
            "24H_DAILY_RANGE_TIER": [w24_lo, w24_mid, w24_hi, b24_lo, b24_hi],
            "MULTI_TOUCH_BODY_CLUSTER": body_clusters,
            "FRACTAL_SWING_SR_FLIP": swing_pivots,
            "IMPULSE_ORDER_BLOCK": order_blocks,
        }

    def analyze_bar(
        self,
        symbol: str,
        pre_candles: Sequence[Sequence[float]],
        reference_price: float | None = None,
    ) -> FractalStructuralAnalysis:
        hist = list(pre_candles[:-1]) if len(pre_candles) > 4 else list(pre_candles)
        cur = pre_candles[-1]
        price = float(reference_price) if reference_price is not None else float(cur[4])

        levels = self.extract_levels_zero_lookahead(pre_candles)

        w72_lo, w72_mid, w72_hi = levels["72H_WICK_OR_BODY_TIER"][:3]
        w24_lo, _w24_mid, w24_hi = levels["24H_DAILY_RANGE_TIER"][:3]

        span72 = max(1e-12, w72_hi - w72_lo)
        span24 = max(1e-12, w24_hi - w24_lo)

        pos_72 = round(((price - w72_lo) / span72) * 100.0, 2)
        pos_24 = round(((price - w24_lo) / span24) * 100.0, 2)
        exp_24_72 = round(span24 / span72, 4)

        rec24 = hist[-24:] if len(hist) >= 24 else hist
        ret_24h = (
            round(((float(cur[4]) - float(rec24[0][4])) / max(1e-12, float(rec24[0][4]))) * 100.0, 2)
            if rec24
            else 0.0
        )
        bounce_24h = round(((float(cur[4]) - w24_lo) / max(1e-12, w24_lo)) * 100.0, 2)

        avg_vol = sum(float(r[5]) for r in rec24) / max(1, len(rec24))
        rvol = round(float(cur[5]) / max(1e-12, avg_vol), 2)

        rec6 = hist[-6:] if len(hist) >= 6 else hist
        broke_6h_hi = float(cur[4]) > max(float(r[2]) for r in rec6)

        # Check naive 72h rolling wick box (1.2% tolerance to w72_lo, w72_mid, w72_hi)
        naive_recalled = any(
            abs(price - lvl) / max(1e-12, price) <= 0.012
            for lvl in (w72_lo, w72_mid, w72_hi)
        )

        # Check multi-scale fractal hierarchy in priority order
        matched_mech = "UNMATCHED_NO_MANS_LAND"
        best_lvl = w72_mid
        best_dist = abs(price - w72_mid) / max(1e-12, price)

        for mech_name, grp in levels.items():
            for lvl in grp:
                d = abs(price - lvl) / max(1e-12, price)
                if d < best_dist:
                    best_dist = d
                    best_lvl = lvl
                if matched_mech == "UNMATCHED_NO_MANS_LAND" and d <= self.touch_tolerance_pct:
                    matched_mech = mech_name

        # Compute next lower structural demand level for ThesisMemoryTracker re-entry
        all_candidates = sorted(
            {
                lvl
                for grp in levels.values()
                for lvl in grp
                if lvl < price * 0.985
            },
            reverse=True,
        )
        lower_demand = all_candidates[0] if all_candidates else round(w72_lo, 8)

        return FractalStructuralAnalysis(
            symbol=symbol,
            matched_mechanism=matched_mech,
            recalled_by_fractal=(matched_mech != "UNMATCHED_NO_MANS_LAND"),
            recalled_by_naive_72h=naive_recalled,
            nearest_level_price=round(best_lvl, 8),
            nearest_level_dist_pct=round(best_dist * 100.0, 3),
            pos_in_72h_range_pct=pos_72,
            pos_in_24h_range_pct=pos_24,
            expansion_24_72_ratio=exp_24_72,
            ret_24h_pct=ret_24h,
            bounce_from_24h_lo_pct=bounce_24h,
            rvol_current=rvol,
            broke_above_6h_high=broke_6h_hi,
            lower_demand_reentry_level=round(lower_demand, 8),
        )

    def evaluate_real_corpus_blind_recall(
        self,
        raw_candles_path: Path | None = None,
    ) -> BlindRecallComparisonReport:
        path = raw_candles_path or DEFAULT_RAW_CANDLES_PATH
        series_list: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        valid = [r for r in series_list if len(r.get("pre_72h_candles", [])) >= 12]

        naive_cnt = 0
        fractal_cnt = 0
        mech_counts: Counter[str] = Counter()
        long_rets: list[float] = []
        short_rets: list[float] = []
        long_bounces: list[float] = []
        short_bounces: list[float] = []

        for row in valid:
            analysis = self.analyze_bar(
                symbol=row["symbol"],
                pre_candles=row["pre_72h_candles"],
                reference_price=row["entry_price_scaled"],
            )
            if analysis.recalled_by_naive_72h:
                naive_cnt += 1
            if analysis.recalled_by_fractal:
                fractal_cnt += 1
            mech_counts[analysis.matched_mechanism] += 1

            if row["direction"] == "LONG":
                long_rets.append(analysis.ret_24h_pct)
                long_bounces.append(analysis.bounce_from_24h_lo_pct)
            else:
                short_rets.append(analysis.ret_24h_pct)
                short_bounces.append(analysis.bounce_from_24h_lo_pct)

        n = max(1, len(valid))
        naive_pct = round((naive_cnt / n) * 100.0, 1)
        fractal_pct = round((fractal_cnt / n) * 100.0, 1)

        return BlindRecallComparisonReport(
            evaluated_real_series=len(valid),
            naive_72h_recalled_count=naive_cnt,
            naive_72h_recall_pct=naive_pct,
            naive_72h_false_reject_pct=round(100.0 - naive_pct, 1),
            fractal_recalled_count=fractal_cnt,
            fractal_recall_pct=fractal_pct,
            mechanism_breakdown=dict(mech_counts),
            long_mean_24h_ret_pct=round(sum(long_rets) / max(1, len(long_rets)), 2),
            short_mean_24h_ret_pct=round(sum(short_rets) / max(1, len(short_rets)), 2),
            long_mean_bounce_from_low_pct=round(sum(long_bounces) / max(1, len(long_bounces)), 2),
            short_mean_bounce_from_low_pct=round(sum(short_bounces) / max(1, len(short_bounces)), 2),
        )
