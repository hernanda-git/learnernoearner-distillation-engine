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

### 2.1 Domain Dataclasses (`proteus.domain.models`)
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
    ENTER = "ENTER"

@dataclass(frozen=True)
class TradeSetup:
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    planned_rr: Decimal
    confidence: float
    archetype: str
```

### 2.2 Invariant Guarantees
1. **Capital Risk Cap**: Never synthesize an order with SL distance $> 5.0\%$ or $< 0.5\%$.
2. **Directional Safety Guard**: Never output a Short signal on a high-beta token if BTC 1D candle is actively expanding upwards.
3. **Execution Mode Separation**: Range setups emit Limit orders; Breakout setups emit Market orders.
