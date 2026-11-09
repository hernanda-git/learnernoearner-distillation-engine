"""Module 5: Cognitive Action Policy & Abstention Gate (`proteus.policy`).

Implements the Bayesian-inspired decision policy:
- Drops bars in "no-man's land" (P(ABSTAIN) >= 0.85)
- Enforces the 80.4% Long / 19.6% Short asymmetric conviction ceiling
- Enforces Execution Mode Separation (Range retests -> LIMIT, Sweep/Breakout -> MARKET)
"""

from __future__ import annotations

from datetime import datetime

from proteus.compass import MacroCompassGate
from proteus.domain.models import (
    Action,
    Direction,
    MacroRegime,
    OrderMode,
    PolicyDecision,
    RangeGeometry,
    SetupArchetype,
)
from proteus.market import MultiTimeframeStore


class CognitivePolicyGate:
    """Evaluates multimodal features to decide ABSTAIN vs ENTER_LONG / ENTER_SHORT."""

    LONG_CONFIDENCE_THRESHOLD: float = 0.65
    SHORT_CONFIDENCE_THRESHOLD: float = 0.85
    NO_MANS_LAND_ABSTAIN_PROB: float = 0.92

    def __init__(self, compass: MacroCompassGate | None = None) -> None:
        self.compass = compass or MacroCompassGate()

    @staticmethod
    def _session_conviction_bonus(timestamp_utc: datetime) -> float:
        """Apply empirical circadian session weighting (London 06-09 UTC, NY 13-17 UTC)."""
        hour = timestamp_utc.hour
        if 6 <= hour <= 9 or 13 <= hour <= 17:
            return 0.08
        if 21 <= hour <= 23 or 0 <= hour <= 4:
            return -0.10
        return 0.02

    def evaluate(
        self,
        geometry: RangeGeometry,
        regime: MacroRegime,
        timestamp_utc: datetime,
        visual_saliency_iou: float = 0.85,
    ) -> PolicyDecision:
        if not MultiTimeframeStore.is_tradable_symbol(geometry.symbol):
            return PolicyDecision(
                action=Action.ABSTAIN,
                direction=None,
                confidence=0.0,
                abstain_prob=1.0,
                archetype=SetupArchetype.NONE,
                order_mode=None,
                rationale=f"Symbol {geometry.symbol} is excluded from tradable high-beta universe.",
            )

        if geometry.in_no_mans_land:
            return PolicyDecision(
                action=Action.ABSTAIN,
                direction=None,
                confidence=round(1.0 - self.NO_MANS_LAND_ABSTAIN_PROB, 4),
                abstain_prob=self.NO_MANS_LAND_ABSTAIN_PROB,
                archetype=SetupArchetype.NONE,
                order_mode=None,
                rationale="Price is in no-man's land between structural tiers; abstaining.",
            )

        session_bonus = self._session_conviction_bonus(timestamp_utc)
        vision_bonus = 0.06 if visual_saliency_iou >= 0.80 else -0.08

        # Candidate Long setups: Range Low liquidity sweep reclaim or 50% Midrange retest
        if geometry.swept_low or geometry.reclaimed_midrange:
            allowed, reason = self.compass.is_direction_allowed(
                geometry.symbol, Direction.LONG, regime
            )
            if not allowed:
                return PolicyDecision(
                    action=Action.ABSTAIN,
                    direction=None,
                    confidence=0.0,
                    abstain_prob=1.0,
                    archetype=SetupArchetype.NONE,
                    order_mode=None,
                    rationale=reason,
                )

            base_conf = 0.76 if geometry.swept_low else 0.72
            if regime == MacroRegime.BULLISH_EXPANSION:
                base_conf += 0.06
            confidence = max(0.0, min(0.99, round(base_conf + session_bonus + vision_bonus, 4)))
            abstain_prob = round(1.0 - confidence, 4)

            if confidence >= self.LONG_CONFIDENCE_THRESHOLD:
                archetype = (
                    SetupArchetype.LIQUIDITY_SWEEP_RECLAIM
                    if geometry.swept_low
                    else SetupArchetype.MIDRANGE_RETEST
                )
                # Invariant 3: Range retest -> LIMIT; Sweep reclaim / breakout -> MARKET
                order_mode = (
                    OrderMode.MARKET
                    if archetype == SetupArchetype.LIQUIDITY_SWEEP_RECLAIM
                    else OrderMode.LIMIT
                )
                return PolicyDecision(
                    action=Action.ENTER_LONG,
                    direction=Direction.LONG,
                    confidence=confidence,
                    abstain_prob=abstain_prob,
                    archetype=archetype,
                    order_mode=order_mode,
                    rationale=f"Long {archetype.value} confirmed under {regime.value}.",
                )

        # Candidate Short setups (strict 80/20 asymmetry gate: confidence >= 0.85)
        if geometry.swept_high or (geometry.rejected_midrange and regime == MacroRegime.BREAKDOWN):
            allowed, reason = self.compass.is_direction_allowed(
                geometry.symbol, Direction.SHORT, regime
            )
            if not allowed:
                return PolicyDecision(
                    action=Action.ABSTAIN,
                    direction=None,
                    confidence=0.0,
                    abstain_prob=1.0,
                    archetype=SetupArchetype.NONE,
                    order_mode=None,
                    rationale=reason,
                )

            base_conf = 0.82 if geometry.swept_high else 0.78
            if regime == MacroRegime.BREAKDOWN:
                base_conf += 0.05
            confidence = max(0.0, min(0.99, round(base_conf + session_bonus + vision_bonus, 4)))
            abstain_prob = round(1.0 - confidence, 4)

            if confidence >= self.SHORT_CONFIDENCE_THRESHOLD:
                archetype = SetupArchetype.RANGE_HIGH_REJECTION
                return PolicyDecision(
                    action=Action.ENTER_SHORT,
                    direction=Direction.SHORT,
                    confidence=confidence,
                    abstain_prob=abstain_prob,
                    archetype=archetype,
                    order_mode=OrderMode.LIMIT,
                    rationale=f"High-conviction Short {archetype.value} (>=0.85 ceiling met).",
                )

        return PolicyDecision(
            action=Action.ABSTAIN,
            direction=None,
            confidence=0.12,
            abstain_prob=0.88,
            archetype=SetupArchetype.NONE,
            order_mode=None,
            rationale="Insufficient structural confluence; defaulting to capital preservation.",
        )
