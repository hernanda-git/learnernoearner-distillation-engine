"""Project Proteus: Air-gapped discretionary trader distillation engine."""

from proteus.domain.models import (
    Action,
    BoundingBox,
    Candle,
    Direction,
    MacroRegime,
    OrderMode,
    PolicyDecision,
    PositionState,
    RangeGeometry,
    SetupArchetype,
    TradeSetup,
    TradeState,
)
from proteus.engine import ProteusDistillationEngine

__version__ = "0.1.0"

__all__ = [
    "Action",
    "BoundingBox",
    "Candle",
    "Direction",
    "MacroRegime",
    "OrderMode",
    "PolicyDecision",
    "PositionState",
    "ProteusDistillationEngine",
    "RangeGeometry",
    "SetupArchetype",
    "TradeSetup",
    "TradeState",
    "__version__",
]
