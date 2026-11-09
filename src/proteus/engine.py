"""End-to-End Project Proteus Distillation Engine Orchestrator (`proteus.engine`)."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Mapping, Optional, Sequence

from proteus.compass import MacroCompassGate
from proteus.constitution import ConstitutionalIdentityGuard, ConstitutionalParameters
from proteus.domain.models import (
    Action,
    Candle,
    MacroRegime,
    PolicyDecision,
    TradeSetup,
)
from proteus.fsm import TradeLifecycleFSM
from proteus.geometry import StructuralGeometryEngine
from proteus.market import MultiTimeframeStore
from proteus.params import OrderParameterSynthesizer
from proteus.policy import CognitivePolicyGate
from proteus.vision import VisualSaliencyAgent

FORBIDDEN_ENV_KEYS: tuple[str, ...] = (
    "BITGET_API_KEY",
    "BITGET_SECRET",
    "BITGET_PASSPHRASE",
    "SECRETCONSTANTS__TRIPLEDESKEY",
    "TRIPLEDES_KEY",
)


class AirGapSecurityError(RuntimeError):
    """Raised if live production credentials leak into the Proteus environment."""


class ProteusDistillationEngine:
    """Coordinated 7-module cognitive distillation pipeline with Constitutional Identity Guard."""

    def __init__(
        self,
        *,
        market: MultiTimeframeStore | None = None,
        compass: MacroCompassGate | None = None,
        geometry: StructuralGeometryEngine | None = None,
        vision: VisualSaliencyAgent | None = None,
        policy: CognitivePolicyGate | None = None,
        params: OrderParameterSynthesizer | None = None,
        fsm: TradeLifecycleFSM | None = None,
        constitution: ConstitutionalParameters | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.verify_air_gap(env if env is not None else os.environ)
        self.constitution = constitution or ConstitutionalParameters()
        ConstitutionalIdentityGuard.validate_parameters(self.constitution)
        self.market = market or MultiTimeframeStore()
        self.compass = compass or MacroCompassGate()
        self.geometry = geometry or StructuralGeometryEngine()
        self.vision = vision or VisualSaliencyAgent()
        self.policy = policy or CognitivePolicyGate(compass=self.compass)
        self.params = params or OrderParameterSynthesizer()
        self.fsm = fsm or TradeLifecycleFSM()

    @staticmethod
    def verify_air_gap(env: Mapping[str, str]) -> None:
        """Enforce Section 1 & Section 5 Credential Isolation Charter."""
        leaked = [key for key in FORBIDDEN_ENV_KEYS if env.get(key)]
        if leaked:
            raise AirGapSecurityError(
                f"Air-gap violation: live production secret keys present in environment: {leaked}"
            )

    def evaluate_bar(
        self,
        symbol: str,
        candles_72h: Sequence[Candle],
        recent_15m_candles: Sequence[Candle],
        btc_daily_candles: Sequence[Candle],
        eth_daily_candles: Sequence[Candle] | None = None,
        live_reference_price: Decimal | None = None,
        visual_saliency_iou: float = 0.88,
    ) -> tuple[MacroRegime, PolicyDecision, Optional[TradeSetup]]:
        """Run the full 7-module cognitive evaluation for a candidate bar."""
        if not recent_15m_candles:
            raise ValueError("recent_15m_candles must not be empty")

        execution_candle = recent_15m_candles[-1]
        regime = self.compass.evaluate_regime(btc_daily_candles, eth_daily_candles)
        range_geom = self.geometry.compute(symbol, candles_72h, execution_candle=execution_candle)

        decision = self.policy.evaluate(
            geometry=range_geom,
            regime=regime,
            timestamp_utc=execution_candle.timestamp_utc,
            visual_saliency_iou=visual_saliency_iou,
        )

        if decision.action == Action.ABSTAIN:
            return regime, decision, None

        setup = self.params.synthesize(
            symbol=symbol,
            decision=decision,
            geometry=range_geom,
            recent_15m_candles=recent_15m_candles,
            live_reference_price=live_reference_price,
        )
        return regime, decision, setup
