"""Cross-Sectional Attention & Relative Strength Filter (`proteus.market.attention`).

Models why `@learnernoearner` selects a specific high-beta coin at time T0 out of
hundreds of perpetuals, discovered via Cohen's d effect-size screening on 10,994
real Bitget 1H candles:
  1. Multi-Day Range Compression (`expansion_24_72 <= 0.72`, Cohen's d = -0.717)
  2. Intraday Relative Volume Surge (`rvol_cur >= 1.35x`, Cohen's d = +0.331)
  3. 6-Hour Micro-Breakout / Midrange Reclaim (`pos_24h` in [0.52, 0.85], `broke_above_6h_hi`)
  4. Parabolic Exhaustion Short Filter (`ret_24h >= +10.0%` & `bounce_from_24h_lo >= +15.0%`)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AttentionScore:
    symbol: str
    score: float  # [0.0, 1.0]
    regime_bias: str  # "LONG_CONTINUATION", "SHORT_EXHAUSTION", "LOW_ATTENTION_ABSTAIN"
    expansion_24_72: float
    rvol_current: float
    ret_24h_pct: float
    bounce_from_24h_lo_pct: float
    pos_24h: float
    broke_above_6h_hi: bool
    rationale: str


class CrossSectionalAttentionScorer:
    """Scores real OHLCV candle arrays for human chart-attention salience."""

    def score_candles(
        self,
        symbol: str,
        pre_candles: Sequence[Sequence[float]],
        hour_utc: int = 14,
    ) -> AttentionScore:
        if len(pre_candles) < 12:
            raise ValueError("pre_candles must contain at least 12 bars")

        hist = list(pre_candles[:-1])
        cur = pre_candles[-1]
        close = float(cur[4])

        w72_hi = max(float(r[2]) for r in hist)
        w72_lo = min(float(r[3]) for r in hist)
        span72 = max(1e-12, w72_hi - w72_lo)

        rec24 = hist[-24:] if len(hist) >= 24 else hist
        w24_hi = max(float(r[2]) for r in rec24)
        w24_lo = min(float(r[3]) for r in rec24)
        span24 = max(1e-12, w24_hi - w24_lo)

        exp_24_72 = round(span24 / span72, 4)
        pos_24 = round((close - w24_lo) / span24, 4)
        ret_24 = round(((close - float(rec24[0][4])) / max(1e-12, float(rec24[0][4]))) * 100.0, 2)
        bounce_24 = round(((close - w24_lo) / max(1e-12, w24_lo)) * 100.0, 2)

        avg_vol = sum(float(r[5]) for r in rec24) / max(1, len(rec24))
        rvol = round(float(cur[5]) / max(1e-12, avg_vol), 2)

        rec6 = hist[-6:] if len(hist) >= 6 else hist
        broke_6h = close > max(float(r[2]) for r in rec6)

        pts = 0.20
        if exp_24_72 <= 0.72:
            pts += 0.25  # Multi-day range compression (Cohen's d = -0.717)
        if rvol >= 1.35:
            pts += 0.20  # Intraday volume attention spike
        if 6 <= hour_utc <= 20:
            pts += 0.15  # Active London/NY waking session

        # Check Short Parabolic Exhaustion vs Long Upper-Equilibrium Reclaim
        if ret_24 >= 8.5 and bounce_24 >= 14.0 and pos_24 < 0.78:
            pts += 0.20
            bias = "SHORT_EXHAUSTION"
            reason = (
                f"Parabolic 24h pump (+{ret_24:.1f}%, +{bounce_24:.1f}% off low) stalling at "
                f"{pos_24*100:.0f}% of 24h range."
            )
        elif 0.48 <= pos_24 <= 0.88 and (broke_6h or rvol >= 1.25):
            pts += 0.20 if broke_6h else 0.12
            bias = "LONG_CONTINUATION"
            reason = (
                f"Compressed range (24h/72h={exp_24_72:.2f}) reclaiming upper-equilibrium "
                f"({pos_24*100:.0f}%) with {rvol:.2f}x RVOL."
            )
        else:
            bias = "LOW_ATTENTION_ABSTAIN"
            reason = "Lacks range-compression reclaim or parabolic exhaustion signature."

        return AttentionScore(
            symbol=symbol,
            score=round(min(0.99, pts), 4),
            regime_bias=bias,
            expansion_24_72=exp_24_72,
            rvol_current=rvol,
            ret_24h_pct=ret_24,
            bounce_from_24h_lo_pct=bounce_24,
            pos_24h=pos_24,
            broke_above_6h_hi=broke_6h,
            rationale=reason,
        )
