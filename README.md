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

- **[Empirical Behavioral Profile](docs/BEHAVIORAL-ANALYSIS.md)**: Quantitative and qualitative breakdown extracted from 784 messages, 97 canonical setups, and 230 chart screenshots.
- **[Distillation Master Plan](docs/MASTER-PLAN.md)**: 7-module decoupled architecture, inverse decision modeling, negative space mining, and phased implementation roadmap.
- **[Architecture & Engine Topology](ARCHITECTURE.md)**: End-to-end event flow, state spaces, action spaces, and FSM lifecycle.

---

## 📊 Key Trader Archetype (Empirical Baseline)

| Dimension | Empirical Finding |
| :--- | :--- |
| **Directional Asymmetry** | **80.4% LONG (78)** vs **19.6% SHORT (19)** |
| **Tradable Universe** | High-beta perps (`WLD`, `PUMP`, `ENA`, `ZEC`, `PENGU`, `INJ`, `MAGIC`, `NEAR`, `PEPE`) |
| **Macro Compass** | `BTC` and `ETH` are never traded; used strictly as higher-timeframe regime filters |
| **Median Stop-Loss** | **2.60%** (anchored 1 tick beyond structural invalidation wick) |
| **Median Target (R:R)** | **4.56R** (single structural destination) |
| **Primary Trading Windows** | **07:00–09:00 UTC** (London Open) & **13:00–17:00 UTC** (New York Open) |
| **In-Flight Management** | Migrates SL to Breakeven (`sl to entry`) at $+1.0R$; derisks before sleep (UTC 21:00+) |

---

## 🚀 Repository Structure

```
learnernoearner-distillation-engine/
├── docs/
│   ├── BEHAVIORAL-ANALYSIS.md      # Empirical profile (784 msgs, 97 setups, 230 charts)
│   └── MASTER-PLAN.md              # 5-phase Project Proteus engineering roadmap
├── scripts/
│   └── extract_corpus_readonly.py  # Air-gapped read-only SQLite/JSONL snapshot extractor
├── src/
│   └── proteus/                    # Autonomous clone engine package
│       ├── domain/                 # Immutable domain models & value objects
│       ├── market/                 # Multi-TF candle lakehouse & negative-space sampler
│       ├── compass/                # BTC/ETH 1D macro regime gate
│       ├── geometry/               # 3-tier 72h range & liquidity sweep detector
│       ├── vision/                 # S/R bounding-box proposer & IoU >= 0.80 gate
│       ├── policy/                 # Bayesian abstention & 80/20 Long-bias policy
│       ├── params/                 # 2.60% SL, 4.56R TP & power-of-10 price scaler
│       ├── fsm/                    # +1.0R breakeven & UTC 21:00+ bedtime trade FSM
│       ├── benchmark/              # Behavioral Parity Score (BPS >= 0.85) Turing harness
│       └── engine.py               # End-to-end 7-module pipeline orchestrator
├── tests/
│   └── test_proteus_engine.py      # Invariant, geometry, FSM, and air-gap test suite
├── ARCHITECTURE.md
├── pyproject.toml
├── README.md
└── .gitignore
```
