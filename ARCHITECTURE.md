# System Architecture: Project Proteus (`learnernoearner-distillation-engine`)

---

## 1. End-to-End Cognitive & Autonomous Evolution Topology

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                     PUBLIC BITGET USDT-FUTURES STREAM                        │
│         • Zero API Keys · 1D Macro · 4H 72h Structure · 15m Execution        │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                 1. MACRO COMPASS GATE (proteus.compass)                      │
│         • Evaluates BTC & ETH 1D (BULLISH_EXPANSION / RANGE_BOUND / BREAKDOWN)│
│         • BTC/ETH never traded directly · Breakdown freezes all Alt Longs    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│        2. 3-TIER STRUCTURAL GEOMETRY & VISION SALIENCY (geometry / vision)   │
│         • 72h Range High (Supply) · 50% Midrange Pivot · Range Low (Demand)  │
│         • 15m Wick Sweep (ratio >= 0.35) · RGB TradingView Box IoU >= 0.80   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│           3. COGNITIVE POLICY & ABSTENTION GATE (proteus.policy)             │
│         • Rule Gate + Fitted 5,091-Bar Gaussian Naive Bayes Classifier       │
│         • Interior "No-Man's Land" -> P(ABSTAIN) = 0.92                      │
│         • Asymmetric Admission: Long >= 0.65 (80.0%) · Short >= 0.85 (20.0%) │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│          4. ASYMMETRIC PARAMETER SYNTHESIZER (proteus.params)                │
│         • Longs: 2.68% Median SL (15 bps below swing low) · 4.89R Target     │
│         • Shorts: 2.17% Median SL (15 bps above wick high) · 4.46R Target    │
│         • Retests -> LIMIT (2 bps Maker) · Sweeps -> MARKET (6 bps Taker)    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│        5. VIRTUAL PAPER EXCHANGE & 2-HOUR IMPULSE FSM (paper / fsm)          │
│         • $1,000 Base · $20 (2.0%)/1R Risk · Max 3 Concurrent Slots          │
│         • +1.0R (~119.1m): Auto "sl to entry" (rescues 61.7% of whipsaws)    │
│         • +1.5R (~123.6m): Auto 50% "tp1 booked"                             │
│         • UTC 21:00+: Bedtime derisk · Full book declines new signals        │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│     6. SELF-MONITOR WATCHDOG & 4-STAGE AI EVOLVER (monitor / evolver / web)  │
│         • 6 Runtime Probes + 6-Cycle Auto-Healing LatchHealer                │
│         • Scout -> AdversarialCritic -> TuringVerifier -> SHA-256 Journal    │
│         • Served Live at https://engine.warga-digital.com (127.0.0.1:18085)  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Subpackage Responsibilities (`src/proteus/`)

| Subpackage | Module Path | Responsibility & Key Classes |
| :--- | :--- | :--- |
| **Domain** | `proteus.domain.models` | Immutable `Candle`, `RangeGeometry`, `BoundingBox`, `PolicyDecision`, `TradeSetup`, `PositionState` |
| **Market** | `proteus.market`, `lakehouse`, `bitget`, `bitget_ws` | `MultiTimeframeStore`, `NegativeSpaceDatasetBuilder` (5,091 bars), `BitgetPublicMarketClient` (8 req/s, retry/429/cache), `BitgetCandleStream` (2 WS legs, 92 candle channels) |
| **Compass** | `proteus.compass` | `MacroCompassGate`: `BTC`/`ETH` 1D regime evaluation and directional admissibility |
| **Geometry** | `proteus.geometry` | `StructuralGeometryEngine`: 72h 3-tier levels, wick rejection ratios, midrange retests, no-man's land |
| **Vision** | `proteus.vision` | `VisualSaliencyAgent`, `TradingViewBoxExtractor`, `VisionCorpusAnalyzer` (284 charts), `SyntheticTradingViewRenderer` |
| **Policy** | `proteus.policy` & `bayesian` | `CognitivePolicyGate` (deterministic) & `BayesianCognitivePolicy` (fitted on 91 usable setups + 5,000 negative bars) |
| **Params** | `proteus.params` | `OrderParameterSynthesizer`: directional SL (`2.68%` / `2.17%`), R:R (`4.89R` / `4.46R`), and $10^k$ meme price scaler |
| **FSM** | `proteus.fsm` | `TradeLifecycleFSM`: $+1.0R$ breakeven shift, UTC 21:00+ bedtime derisking, linguistic command translator |
| **Benchmark** | `proteus.benchmark` | `BehavioralParityBenchmark`: evaluates $BPS = 0.35 S_{\text{action}} + 0.25 S_{\text{spatial}} + 0.25 S_{\text{abstain}} + 0.15 S_{\text{timing}}$ |
| **Replay** | `proteus.replay` | `EmpiricalCorpusReplay`: replays 784 messages, 95 setups, and 47 management updates (BPS `None`, unmeasured) |
| **Backtest** | `proteus.backtest` | `LifecycleBacktestSimulator`: candle-driven Naive vs. FSM + 86-signal real-candle whipsaw audit |
| **Shadow** | `proteus.shadow` & `lead_time` | `ForwardShadowScanner` (live Bitget scan) & `ShadowLeadTimeComparator` (unmeasured until detections are logged) |
| **Paper** | `proteus.paper` | `VirtualPaperExchange`: `$1,000` ledger, Bitget Maker/Taker fees (`2 bps`/`6 bps`), 3-slot cap (no eviction churn) |
| **Constitution** | `proteus.constitution` | `ConstitutionalIdentityGuard` (AST anti-indicator scanner + corridors) & `BoundedSelfCorrector` |
| **Monitor** | `proteus.monitor` | `SelfMonitoringWatchdog`: active-path runtime probes (idle paths report `SKIP`) + 6-cycle `LatchHealer` recovery |
| **Evolver** | `proteus.evolver` | `AgenticSelfImprover` (`TelemetryScout` → `AdversarialCritic` → `TuringVerifier` → `HashChainCommitter`) |
| **Web UI** | `proteus.web` | `ProteusWebHandler` & `INDEX_HTML`: 7-tab institutional dark-mode console on `127.0.0.1:18085` |

---

## 3. Hard Invariant Guarantees

1. **Air-Gap Credential Guard**: `ProteusDistillationEngine.verify_air_gap()` aborts immediately with `AirGapSecurityError` if `BITGET_API_KEY`, `BITGET_SECRET`, `BITGET_PASSPHRASE`, or `TRIPLEDES` environment variables exist.
2. **Codebase Anti-Indicator Purity**: `ConstitutionalIdentityGuard.verify_codebase_purity()` scans all `.py` files in `src/proteus/` and raises `IdentityDriftError` if any lagging retail oscillator (`RSI`, `MACD`, `Bollinger`, `Stochastic`, `Ichimoku`, `EMA/SMA crossover`) is introduced.
3. **Capital Risk Cap**: Synthesized orders enforce $0.50\% \le \text{SL distance} \le 5.00\%$, anchored $15\text{ bps}$ beyond the 15m invalidation swing wick.
4. **Directional Safety Guard**: `BTC` and `ETH` are never traded directly; high-beta Longs freeze during `BTC` 1D `BREAKDOWN`, and high-beta Shorts freeze during `BTC` 1D `BULLISH_EXPANSION`.
5. **Execution Mode Separation**: Structural retests (`MIDRANGE_RETEST`, `RANGE_HIGH_REJECTION`) emit `OrderMode.LIMIT` (`2.0 bps` Maker); liquidity sweeps (`LIQUIDITY_SWEEP_RECLAIM`) emit `OrderMode.MARKET` (`6.0 bps` Taker).
6. **Constitutional Self-Correction Rollback**: `BoundedSelfCorrector` and `AgenticSelfImprover` automatically reject and roll back any parameter update that violates `CONSTITUTIONAL_CORRIDORS` or drops $BPS < 0.85$.

---

## 4. Trading Core: Alpha Engine (`proteus.alpha`)

The distillation pipeline above is **research + telemetry**. The trading path is
a separate, portfolio-level engine validated in `docs/ALPHA-RESEARCH.md`.

```text
Bitget public 4H panel (RWA excluded)
        │
        ▼
daily UTC bars ──► rolling vol / ATR / SMA / 14-60d momentum
        │
        ▼
BTC 200d SMA × 1.02 + 60d momentum gate ──► risk-off = 100% cash
        │
        ▼
top 8 positive-momentum coins above SMA50
        │
        ▼
inverse-vol weights · 15% vol target · 2x gross cap · 25% asset cap
        │
        ▼
weekly calendar-anchored rebalance · 4x ATR stops · 30% circuit breaker
        │
        ▼
alpha_ledger.json + alpha_closed_trades.jsonl + /api/v1/alpha
```

| Module | Responsibility |
|---|---|
| `alpha/panel.py` | 4H JSONL → completed UTC daily bars; resilient to partial files |
| `alpha/signals.py` | O(N) rolling volatility, ATR, SMA, momentum, dollar volume |
| `alpha/portfolio.py` | `AlphaConfig`, eligibility, time-series score, regime gate, weights, vol targeting |
| `alpha/simulator.py` | Open-to-open backtest, fees, funding, ATR stops, drawdown breaker |
| `alpha/metrics.py` | Drawdowns, deflated Sharpe, CSCV PBO, block bootstrap |
| `alpha/research.py` | 16-config grid, walk-forward, holdout, benchmarks, report JSON |
| `alpha/live.py` | Daily paper book, panel cache, RWA-filtered universe, atomic ledger |

**Hard invariants of the trading core**

1. **No look-ahead.** A backtest target is computed at the close of day `d` and
   executed at the open of `d + 1`. The live book uses the last completed daily
   close and the latest 4H mark.
2. **No RWA.** `isRwa == "YES"` contracts (tokenized stocks, ETFs, commodities)
   are excluded before selection. The universe fails closed if contract
   classification is unavailable.
3. **No slot churn.** At most one rebalance per UTC day; positions are carried
   between rebalances and never evicted to make room for a new signal.
4. **Calendar anchoring.** Rebalance days are a function of the UTC date, so a
   full run and a single-year run hold the book on the same days.
5. **Explicit costs.** 8 bps/side plus funding are charged in every backtest and
   in the live ledger; the 3× stress case remains profitable.
6. **Long-only.** Crypto short legs are squeeze-prone; `allow_shorts=False` in
   the frozen core.
