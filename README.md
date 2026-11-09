# Project Proteus: Trader Distillation Engine

> **Autonomous Cognitive Cloning of Discretionary Crypto Signal Provider (`@learnernoearner`)**  
> Air-gapped, independent research and execution engine. Zero coupling with production trading bots.

---

## 🎯 Mission Statement

To distill the implicit market heuristics, visual chart perception, and risk management of human discretionary trader `@learnernoearner` into an autonomous, 1:1 behavioral decision engine.

Unlike naive indicator bots (which fit lagging moving averages or static RSI levels), **Project Proteus** models the trader as a **Bayesian belief-updating cognitive agent** operating under bounded rationality, visual chart saliency, asymmetric loss aversion, and selective abstention.

---

## 🛡️ Air-Gap & Safety Guarantees

This repository is **completely decoupled and isolated** from the live Bitget production trading system (`fatty-multi-exchange-trader`):
- **Zero Shared Infrastructure**: Operates on local DuckDB / Parquet data lakes; never connects to live trading database sockets.
- **Zero Live Secrets**: Bitget API keys, HMAC secrets, and 3DES keys are strictly barred from this environment.
- **Synthetic Simulation**: All validation and parameter tuning occur in virtual tick-level paper simulation.

---

## 📚 Core Architecture & Documentation

- **[Constitutional Identity Charter](IDENTITY.md)**: Immutable anti-drift rules, 7 cognitive pillars, and bounded self-correction corridors.
- **[Empirical Behavioral Profile](docs/BEHAVIORAL-ANALYSIS.md)**: Quantitative and qualitative breakdown extracted from 784 messages, 97 canonical setups, and 284 chart screenshots.
- **[Distillation Master Plan](docs/MASTER-PLAN.md)**: 7-module decoupled architecture, inverse decision modeling, negative space mining, and phased implementation roadmap.
- **[Architecture & Engine Topology](ARCHITECTURE.md)**: End-to-end event flow, state spaces, action spaces, and FSM lifecycle.
---

## 📊 Key Trader Archetype (Empirical Baseline)

| Dimension | Empirical Finding ($N = 784\text{ msgs}, 97\text{ setups}, 47\text{ updates}$) |
| :--- | :--- |
| **Directional Asymmetry** | **80.4% LONG (78)** vs **19.6% SHORT (19)** |
| **Directional SL Geometry** | **2.60% overall median** — **2.67% on Longs** vs **2.17% on Shorts** (tighter invalidation at Range High) |
| **Directional Target (R:R)** | **4.80R overall median** — **4.87R on Longs** ($P_{90} = 9.40R$) vs **4.46R on Shorts** ($P_{90} = 6.01R$) |
| **2-Hour Impulse Coupling** | **`SL_TO_ENTRY` at 119.1m** ($1.98\text{h}$) & **`TP1_BOOKED` at 123.6m** ($2.06\text{h}$) — coupled to the first 8 bars ($15\text{m}$) |
| **Multi-Session Runner Hold** | **`TP_BOOKED` at 2,235.5m** ($37.3\text{h} \approx 1.55\text{d}$) · **`CLOSE` (early/bedtime) at 540.3m** ($9.0\text{h}$) |
| **784-Message Taxonomy** | $12.2\%$ Entry Signals (96) · $16.8\%$ In-Flight Mgmt (132) · $11.9\%$ Macro/Range (93) · $59.1\%$ Abstain/Commentary (463) |

---

## 🚀 Repository Structure

```
learnernoearner-distillation-engine/
├── benchmarks/
│   ├── corpus/                              # Air-gapped empirical snapshot
│   │   ├── canonical_signals.json           # 97 canonical trade setups
│   │   ├── management_updates.json          # 47 in-flight management actions
│   │   ├── telegram_messages.json           # 784 raw Telegram messages
│   │   ├── signal_candle_trajectories.json  # 87 real Bitget 1H [T0-72h, T0+48h] audits
│   │   └── vision_annotations.json          # 284 real TradingView chart CV extractions
│   ├── live_shadow_snapshot.json            # Real-time Phase 5 Bitget USDT-FUTURES scan
│   └── paper_ledger.json                    # Virtual Paper Exchange active position ledger
├── docs/
│   ├── BEHAVIORAL-ANALYSIS.md               # Empirical profile & cognitive framework
│   └── MASTER-PLAN.md                       # 5-phase Project Proteus engineering roadmap
├── scripts/
│   ├── extract_corpus_readonly.py           # Air-gapped read-only SQLite/JSONL extractor
│   ├── run_turing_benchmark.py              # Phases 1–4 Turing replay, Bayes & backtest CLI
│   ├── run_shadow_daemon.py                 # Phase 5 live public-REST forward shadow scanner
│   └── run_paper_trader.py                  # Stateful Virtual Paper Exchange runner
├── src/
│   └── proteus/                             # Autonomous clone engine package
│       ├── domain/                          # Immutable domain models & value objects
│       ├── market/                          # Multi-TF lakehouse, 5000-bar miner & REST client
│       ├── compass/                         # BTC/ETH 1D macro regime gate
│       ├── geometry/                        # 3-tier 72h range & liquidity sweep detector
│       ├── vision/                          # RGB TradingView box extractor & 284-chart analyzer
│       ├── policy/                          # Rule policy + fitted 5097-bar Bayesian classifier
│       ├── params/                          # Directional SL (2.67%/2.17%), R:R & 10^k scaler
│       ├── fsm/                             # +1.0R breakeven & UTC 21:00+ bedtime trade FSM
│       ├── benchmark/                       # Behavioral Parity Score (BPS >= 0.85) harness
│       ├── replay/                          # 97-signal & 784-message empirical replay engine
│       ├── backtest/                        # 97-setup backtester + real-candle whipsaw audit
│       ├── shadow/                          # Live zero-key Bitget USDT-FUTURES shadow scanner
│       ├── paper/                           # Stateful Virtual Paper Exchange ($1,000 ledger)
│       ├── constitution/                    # ConstitutionalIdentityGuard & BoundedSelfCorrector
│       └── engine.py                        # End-to-end 7-module pipeline orchestrator
├── tests/
│   └── test_proteus_engine.py               # 18-test invariant, CV, Bayes, audit, paper & identity suite
├── AGENTS.md                                # Mandatory anti-drift rules for AI coding agents
├── ARCHITECTURE.md
├── IDENTITY.md                              # Immutable project identity & bounded self-correction charter
├── pyproject.toml
├── README.md
└── .gitignore
```
