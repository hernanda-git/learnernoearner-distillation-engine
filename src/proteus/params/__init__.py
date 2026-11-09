"""Module 6: Order Parameter Synthesizer & Price Scaler (`proteus.params`).

Synthesizes structural Stop-Loss (median 2.60%, 1 tick outside invalidation wick),
single structural Take-Profit (median 4.56R), and power-of-10 meme price scaling.
Enforces Architecture Invariant 1 (0.50% <= SL distance <= 5.00%).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from proteus.domain.models import (
    Action,
    Candle,
    Direction,
    OrderMode,
    PolicyDecision,
    RangeGeometry,
    TradeSetup,
)
from proteus.market import normalize_base_symbol


class OrderParameterSynthesizer:
    """Synthesizes execution parameters adhering to empirical risk geometry."""

    MEDIAN_SL_PCT: Decimal = Decimal("0.0260")
    MEDIAN_SL_LONG_PCT: Decimal = Decimal("0.0267")
    MEDIAN_SL_SHORT_PCT: Decimal = Decimal("0.0217")
    MEDIAN_TARGET_RR: Decimal = Decimal("4.56")
    MEDIAN_RR_LONG: Decimal = Decimal("4.87")
    MEDIAN_RR_SHORT: Decimal = Decimal("4.46")
    TICK_BUFFER_PCT: Decimal = Decimal("0.0015")
    MIN_SL_PCT: Decimal = Decimal("0.0050")
    MAX_SL_PCT: Decimal = Decimal("0.0500")

    @staticmethod
    def resolve_power_of_10_scale(
        quoted_price: Decimal,
        live_reference_price: Decimal | None,
    ) -> tuple[Decimal, int]:
        """Align shorthand meme-token prices (e.g. PEPE 0.51 vs 0.0000051 or 0.0051).

        Returns (aligned_price, scale_exponent_base10).
        """
        if live_reference_price is None or live_reference_price <= Decimal("0") or quoted_price <= Decimal("0"):
            return quoted_price, 1

        best_price = quoted_price
        best_factor = 1
        best_rel_err = abs(quoted_price - live_reference_price) / live_reference_price

        for exp in range(-8, 9):
            if exp == 0:
                continue
            factor_dec = Decimal(10) ** Decimal(exp)
            candidate = quoted_price * factor_dec
            rel_err = abs(candidate - live_reference_price) / live_reference_price
            if rel_err < best_rel_err and rel_err <= Decimal("0.20"):
                best_rel_err = rel_err
                best_price = candidate
                best_factor = int(Decimal(10) ** abs(exp))
        return best_price, best_factor

    def synthesize(
        self,
        symbol: str,
        decision: PolicyDecision,
        geometry: RangeGeometry,
        recent_15m_candles: Sequence[Candle],
        live_reference_price: Decimal | None = None,
    ) -> TradeSetup:
        if decision.action == Action.ABSTAIN or decision.direction is None or decision.order_mode is None:
            raise ValueError("Cannot synthesize TradeSetup for an ABSTAIN policy decision")

        if not recent_15m_candles:
            raise ValueError("recent_15m_candles required for swing wick anchor")

        base = normalize_base_symbol(symbol)
        raw_entry = recent_15m_candles[-1].close
        entry_price, scale_factor = self.resolve_power_of_10_scale(raw_entry, live_reference_price)

        lookback = recent_15m_candles[-8:] if len(recent_15m_candles) >= 8 else recent_15m_candles

        if decision.direction == Direction.LONG:
            swing_low, _ = self.resolve_power_of_10_scale(
                min(c.low for c in lookback), live_reference_price
            )
            candidate_sl = swing_low - (entry_price * self.TICK_BUFFER_PCT)
            raw_risk_pct = (entry_price - candidate_sl) / entry_price
            if raw_risk_pct < self.MIN_SL_PCT or raw_risk_pct > self.MAX_SL_PCT:
                # Clamp to empirical median 2.60% when local wick violates Invariant 1
                risk_pct = max(self.MIN_SL_PCT, min(self.MAX_SL_PCT, self.MEDIAN_SL_PCT))
                stop_loss = entry_price * (Decimal("1") - risk_pct)
            else:
                risk_pct = raw_risk_pct
                stop_loss = candidate_sl

            risk_abs = entry_price - stop_loss
            take_profit = entry_price + (self.MEDIAN_TARGET_RR * risk_abs)
            limit_low = (
                (entry_price - risk_abs * Decimal("0.25")).quantize(Decimal("0.00000001"))
                if decision.order_mode == OrderMode.LIMIT
                else None
            )
            limit_high = entry_price if decision.order_mode == OrderMode.LIMIT else None
        else:
            swing_high, _ = self.resolve_power_of_10_scale(
                max(c.high for c in lookback), live_reference_price
            )
            candidate_sl = swing_high + (entry_price * self.TICK_BUFFER_PCT)
            raw_risk_pct = (candidate_sl - entry_price) / entry_price
            if raw_risk_pct < self.MIN_SL_PCT or raw_risk_pct > self.MAX_SL_PCT:
                risk_pct = max(self.MIN_SL_PCT, min(self.MAX_SL_PCT, self.MEDIAN_SL_PCT))
                stop_loss = entry_price * (Decimal("1") + risk_pct)
            else:
                risk_pct = raw_risk_pct
                stop_loss = candidate_sl

            risk_abs = stop_loss - entry_price
            take_profit = entry_price - (self.MEDIAN_TARGET_RR * risk_abs)
            limit_low = entry_price if decision.order_mode == OrderMode.LIMIT else None
            limit_high = (
                (entry_price + risk_abs * Decimal("0.25")).quantize(Decimal("0.00000001"))
                if decision.order_mode == OrderMode.LIMIT
                else None
            )

        planned_rr = (abs(take_profit - entry_price) / abs(entry_price - stop_loss)).quantize(
            Decimal("0.01")
        )
        risk_pct_display = (risk_pct * Decimal("100")).quantize(Decimal("0.01"))

        return TradeSetup(
            symbol=base,
            direction=decision.direction,
            order_mode=decision.order_mode,
            entry_price=entry_price.quantize(Decimal("0.00000001")),
            stop_loss=stop_loss.quantize(Decimal("0.00000001")),
            take_profit=take_profit.quantize(Decimal("0.00000001")),
            planned_rr=planned_rr,
            risk_pct=risk_pct_display,
            confidence=decision.confidence,
            archetype=decision.archetype,
            limit_band_low=limit_low,
            limit_band_high=limit_high,
            scale_factor=scale_factor,
        )
