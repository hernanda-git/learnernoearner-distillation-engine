# System Architecture: Project Proteus

---

## 1. High-Level Topology

```
┌────────────────────────────────────────────────────────┐
│               MULTI-TIMEFRAME DATA STREAM              │
│       • Public CCXT / Binance / Bitget REST / WS       │
│       • 1D Structure · 4h Swings · 15m Execution       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               MACRO COMPASS (BTC / ETH)                │
│       • 1D Trend Filter (Expansion vs Compression)     │
│       • If BTC breakdown ──▶ Inhibit All Alt Longs     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            3-TIER STRUCTURAL GEOMETRY CORE             │
│       • Range High / Low (72h extreme wicks)           │
│       • 50% Mid Range Equilibrium                      │
│       • Liquidity Sweeps past Session Extremes         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            VISUAL SALIENCY & ATTENTION AGENT           │
│       • Generates clean TradingView candlestick image  │
│       • Predicts S/R bounding boxes (IoU >= 0.80)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│         COGNITIVE POLICY & ABSTENTION GATE             │
│       • Evaluates P(ABSTAIN) vs P(ENTER)               │
│       • Enforces 80/20 Long-Bias Ceiling               │
│       • Drops 95% of bars in "no-man's land"           │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             ORDER PARAMETER SYNTHESIZER                │
│       • Median 2.60% Stop-Loss (1 tick outside wick)   │
│       • Median 4.56R Take-Profit Structural Target     │
│       • Power-of-10 Price Scaler for meme tokens       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            IN-FLIGHT TRADE MANAGEMENT FSM              │
│       • Migrates SL to Breakeven at +1.0R              │
│       • Derisks before sleep (UTC 21:00+)              │
│       • Logs tick-level execution telemetry            │
└────────────────────────────────────────────────────────┘
```

---

## 2. Component Contract & Interfaces

### 2.1 Domain Models (`proteus.domain.models`)
```python
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class Action(str, Enum):
    ABSTAIN = "ABSTAIN"
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"

class OrderMode(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class MacroRegime(str, Enum):
    BULLISH_EXPANSION = "BULLISH_EXPANSION"
    RANGE_BOUND = "RANGE_BOUND"
    BREAKDOWN = "BREAKDOWN"

class SetupArchetype(str, Enum):
    MIDRANGE_RETEST = "MIDRANGE_RETEST"
    LIQUIDITY_SWEEP_RECLAIM = "LIQUIDITY_SWEEP_RECLAIM"
    RANGE_HIGH_REJECTION = "RANGE_HIGH_REJECTION"
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    NONE = "NONE"

@dataclass(frozen=True)
class TradeSetup:
    symbol: str
    direction: Direction
    order_mode: OrderMode
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    planned_rr: Decimal
    risk_pct: Decimal
    confidence: float
    archetype: SetupArchetype
    limit_band_low: Optional[Decimal] = None
    limit_band_high: Optional[Decimal] = None
    scale_factor: int = 1
```

### 2.2 Module Responsibilities

| Module | Package Path | Core Responsibility |
| :--- | :--- | :--- |
| **1. Lakehouse** | `proteus.market` | High-beta universe filter, $[T_0-30\text{d}, T_0+48\text{h}]$ alignment, negative-space mining |
| **2. Macro Compass** | `proteus.compass` | `BTC`/`ETH` 1D regime evaluation (`BULLISH_EXPANSION`, `RANGE_BOUND`, `BREAKDOWN`) |
| **3. Geometry Core** | `proteus.geometry` | 72h Range High/Low, $50\%$ Midrange equilibrium, wick sweep & no-man's land detection |
| **4. Vision Saliency** | `proteus.vision` | S/R consolidation bounding-box proposal & spatial parity check ($\text{IoU} \ge 0.80$) |
| **5. Policy Gate** | `proteus.policy` | $P(\text{ABSTAIN})$ filter, $80.4\%$ Long ($\ge 0.65$) vs $19.6\%$ Short ($\ge 0.85$) asymmetry |
| **6. Synthesizer** | `proteus.params` | $2.60\%$ structural SL ($15\text{ bps}$ wick buffer), $4.56R$ single TP, $10^k$ meme price scaler |
| **7. Lifecycle FSM** | `proteus.fsm` | $+1.0R$ breakeven shift (`sl to entry`), UTC 21:00+ bedtime derisking, lexicon commands |
| **8. Turing Harness** | `proteus.benchmark` | Behavioral Parity Score ($BPS \ge 0.85$) across action, spatial, abstention, and timing |

### 2.3 Hard Invariant Guarantees
1. **Air-Gap Credential Guard**: `ProteusDistillationEngine.verify_air_gap()` aborts immediately if `BITGET_API_KEY`, `BITGET_SECRET`, `BITGET_PASSPHRASE`, or `TRIPLEDES` environment variables are present.
2. **Capital Risk Cap**: Synthesized orders enforce $0.50\% \le \text{SL distance} \le 5.00\%$, anchored $15\text{ bps}$ outside the 15m invalidation wick (defaulting to the $2.60\%$ empirical median when local wicks violate bounds).
3. **Directional Safety Guard**: `BTC` and `ETH` are never traded directly; high-beta Longs freeze during `BTC` 1D `BREAKDOWN`, and high-beta Shorts freeze during `BTC` 1D `BULLISH_EXPANSION`.
4. **Execution Mode Separation**: Structural retests (`MIDRANGE_RETEST`, `RANGE_HIGH_REJECTION`) emit `OrderMode.LIMIT`; liquidity sweeps (`LIQUIDITY_SWEEP_RECLAIM`) emit `OrderMode.MARKET`.
