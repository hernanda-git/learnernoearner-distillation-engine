"""Module 2: Macro Compass Gate (`proteus.compass`).

BTC and ETH are never traded directly; they act strictly as higher-timeframe
regime gates for high-beta altcoin admission.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from proteus.domain.models import Candle, Direction, MacroRegime
from proteus.market import MACRO_COMPASS_ASSETS, normalize_base_symbol


class MacroCompassGate:
    """Evaluates BTC/ETH 1D structure to gate directional altcoin trades."""

    def evaluate_regime(
        self,
        btc_daily_candles: Sequence[Candle],
        eth_daily_candles: Sequence[Candle] | None = None,
    ) -> MacroRegime:
        """Compute macro regime from 3-day BTC (and optional ETH) daily candles.

        Formula (docs/MASTER-PLAN.md Section 2, Module 2):
        - BREAKDOWN: P_BTC < Support_1D (prior 3-day structural low) -> FREEZE_ALL_LONGS
        - BULLISH_EXPANSION: P_BTC > DailyOpen and Close_1D > P_mid_3d -> inhibit alt Shorts
        - RANGE_BOUND: P_low_3d <= P_BTC <= P_high_3d
        """
        if not btc_daily_candles:
            return MacroRegime.RANGE_BOUND

        window = btc_daily_candles[-4:] if len(btc_daily_candles) >= 4 else btc_daily_candles
        current = window[-1]
        prior = window[:-1] if len(window) > 1 else window

        support_1d = min(c.low for c in prior)
        high_3d = max(c.high for c in prior)
        mid_3d = (high_3d + support_1d) / Decimal(2)

        if current.close < support_1d:
            return MacroRegime.BREAKDOWN

        if eth_daily_candles and len(eth_daily_candles) >= 2:
            eth_prior_low = min(c.low for c in eth_daily_candles[-4:-1] or eth_daily_candles[:-1])
            if eth_daily_candles[-1].close < eth_prior_low:
                return MacroRegime.BREAKDOWN

        if current.close > current.open and current.close > mid_3d:
            return MacroRegime.BULLISH_EXPANSION

        return MacroRegime.RANGE_BOUND

    def is_direction_allowed(
        self,
        symbol: str,
        direction: Direction,
        regime: MacroRegime,
    ) -> tuple[bool, str]:
        """Enforce Macro Compass rules and Architecture Invariant 2."""
        base = normalize_base_symbol(symbol)
        if base in MACRO_COMPASS_ASSETS:
            return (
                False,
                f"{base} is a Macro Compass anchor and is never traded directly.",
            )

        if regime == MacroRegime.BREAKDOWN and direction == Direction.LONG:
            return (
                False,
                "BTC 1D support breakdown active: all altcoin Long entries are frozen.",
            )

        if regime == MacroRegime.BULLISH_EXPANSION and direction == Direction.SHORT:
            return (
                False,
                "Invariant 2: Shorting high-beta alts is prohibited during BTC 1D bullish expansion.",
            )

        return True, f"Macro regime {regime.value} permits {direction.value} on {base}."
