# Project Proteus: Trader Distillation Engine (`@learnernoearner`)

> **Live Web Console**: [`https://engine.warga-digital.com`](https://engine.warga-digital.com) (`127.0.0.1:18085` · 24/7 Systemd Daemon)  
> **Companion Copy-Trader**: [`https://trade.warga-digital.com`](https://trade.warga-digital.com) (`fatty-multi-exchange-trader` · `:18081`)  
> **Isolation Charter**: 100% air-gapped cognitive clone. Zero live Bitget API keys, zero HMAC/3DES secrets, zero production DB write sockets.

---

## 🎯 Mission & Paradigm

**Project Proteus** reverse-engineers the implicit market heuristics, 3-tier horizontal range perception, visual chart saliency, and intraday risk management of discretionary crypto trader `@learnernoearner` into an autonomous, self-monitoring, self-improving decision engine.

Unlike reactive copy-trading (which suffers $6\text{–}28\text{s}$ human screenshot/typing lag and **56.5% survivorship silence** on unannounced stop-outs) or naive retail indicator bots (which curve-fit lagging oscillators like RSI/MACD), Project Proteus models the human as a **Bayesian structural range & liquidity agent** governed by four empirical laws:
1. **Macro Compass Separation (`proteus.compass`)**: `BTC` and `ETH` are never traded directly; their 1D candles gate directional admission across high-beta perpetuals (`WLD`, `PUMP`, `ENA`, `ZEC`, `INJ`, `PENGU`, `MAGIC`, `NEAR`, `GRASS`, `PEPE`, `SNDK`, `TRUMP`).
2. **72-Hour 3-Tier Range & Abstention First (`proteus.geometry`, `proteus.policy`)**: Price is mapped against 72h `Range High`, `50% Mid Range`, and `Range Low`. Over **85%–98%** of intraday bars floating in interior "no-man's land" are dropped ($P(\text{ABSTAIN}) = 0.92$).
3. **Directional Conviction & Stop/Target Asymmetry (`proteus.params`)**:
   - **80.4% LONG (78)** ($\theta_{\text{Long}} \ge 0.65$, **2.67% median SL**, **4.87R median TP**) vs. **19.6% SHORT (19)** ($\theta_{\text{Short}} \ge 0.85$, **2.17% median SL**, **4.46R median TP**).
   - Structural retests emit **`LIMIT`** orders (`2.0 bps` Maker fee); liquidity sweep reclaims emit **`MARKET`** orders (`6.0 bps` Taker fee).
4. **The 2-Hour Coupled Impulse FSM (`proteus.fsm`)**:
   - Real Bitget 1H candle forensics (`87` resolved setups) proved that while **54.0% ($47/87$)** reach $+1.0R$ before SL, **61.7% ($29/47$) of those $+1.0R$ winners reverse to the original SL within 48 hours**.
   - Migrating `SL → Entry` at **$+1.0R$ (`119.1m` median)** and booking $50\%$ at **`TP1` (`123.6m` median)** rescues all 29 whipsaws, cutting full stop-out losses from **68.0% down to 11.3%**, cutting Max Drawdown from **15.14R (`30.28%`) to 2.00R (`4.00%`)**, and boosting Profit Factor from **2.48 to 10.08** (`$1,000 → $2,938.51` net after Bitget fees).

---

## 📚 Core Documentation Index

- **[Constitutional Identity Charter](IDENTITY.md)**: Immutable anti-drift manifesto, 7 cognitive pillars, 5 forbidden anti-identities, and hard self-correction corridors.
- **[AI Agent Instructions](AGENTS.md)**: Mandatory startup rules for coding agents operating in this repository.
- **[System Architecture & Module Contracts](ARCHITECTURE.md)**: End-to-end 12-subpackage topology, domain dataclasses, and hard invariant guarantees.
- **[Empirical Behavioral & Forensic Analysis](docs/BEHAVIORAL-ANALYSIS.md)**: Complete quantitative & qualitative profile across 784 Telegram messages, 97 canonical setups, 47 management actions, 87 Bitget 1H candle trajectories, and 284 TradingView chart screenshots.
- **[Engineering Master Plan (Phases 1–6 Complete)](docs/MASTER-PLAN.md)**: Implemented architecture, Cognitive Turing Test scorecard ($BPS = 0.9700$), and Phase 7 Canary Graduation criteria.
- **[Operations & Deployment Runbook](docs/OPERATIONS-RUNBOOK.md)**: Production runbook for `https://engine.warga-digital.com`, `systemd` services, OpenLiteSpeed + Cloudflare routing, REST API endpoints, CLI modes, and Operator Action Gates.

---

## 📊 Empirical & Benchmark Summary (`581e1b7`+)

| Benchmark / Forensic Dimension | Scope | Verified Result | Gate / Baseline |
| :--- | :--- | ---: | :--- |
| **Behavioral Parity Score ($BPS$)** | 784 msgs · 97 setups · 47 updates | **0.9700** | $\ge 0.8500$ (**PASSED**) |
| **5,097-Bar Bayesian Policy Abstention** | 5,000 negative bars + 97 signals | **100.0% Acc / 100.0% Recall** | $\ge 95.0\%$ (**PASSED**) |
| **Shadow Lead-Time Parity ($\Delta t$)** | 25 recent canonical setups | **−16.5s median lead** | $\le 0.0\text{s}$ (**100% front-run**) |
| **284-Chart Computer Vision Pass** | 216 Light (76.1%) · 68 Dark (23.9%) | **83.8% R:R boxes · 45.4% S/R** | $\text{IoU} \ge 0.80$ (**PASSED**) |
| **$1,000 Paper Sim (97 Setups, Net of Fees)** | `$20/1R` risk · `$59.69` Bitget fees | **$2,938.51 (+193.9% net)** | `PF = 10.08 · Max DD = 4.0%` |
| **Constitutional Codebase Purity** | All `src/proteus/` Python modules | **26/26 files pure** | Zero retail oscillators (**PASSED**) |
| **Automated Test Suite (`pytest`)** | 21 unit, invariant, CV & replay tests | **21/21 passed (1.63s)** | `100% pass` (**PASSED**) |

---

## ⏱️ Operator Action Gates (When to Act)

1. **Daily Intraday Observation Windows (Hands-Off)**:
   - **London Open (`06:00–09:00 UTC` / `13:00–16:00 WIB`)** & **New York Open (`13:00–17:00 UTC` / `20:00–00:00 WIB`)**: Observe live 5-minute ticks, `+1.0R` breakeven shifts, and 3-slot margin velocity rotations on [`https://engine.warga-digital.com`](https://engine.warga-digital.com) (Tab 1).
   - **Bedtime Derisk Gate (`21:00–23:59 UTC` / `04:00–06:59 WIB`)**: Verify profitable open positions transition to `BEDTIME_DERISKED` or `CLOSED_EARLY`.
2. **Forward Shadow Graduation Gate (`2026-11-16` or `closed_positions_count >= 15`)**:
   - Once the 24/7 paper ledger closes **$\ge 15$ forward trades** with **Win + Scratch Rate $\ge 75\%$**, **Max Drawdown $\le 3.5R$ (`7.0%`)**, and **Self-Monitor Status = `HEALTHY`**, promote Proteus to a canary signal producer (`$1–$2` risk/trade).
3. **Early Intervention Triggers**:
   - Act early only if **Tab 7 Watchdog** flips to `LATCHED_HALT`, if `@learnernoearner` introduces a new recurring ticker outside `TRADABLE_UNIVERSE`, or after every ~25 new human signals to run an updated corpus extraction.

---

## 🚀 Repository Structure

```text
learnernoearner-distillation-engine/
├── benchmarks/
│   ├── corpus/                              # Air-gapped empirical ground-truth corpus
│   │   ├── canonical_signals.json           # 97 canonical trade setups
│   │   ├── management_updates.json          # 47 in-flight management actions
│   │   ├── telegram_messages.json           # 784 raw Telegram messages
│   │   ├── signal_candle_trajectories.json  # 87 real Bitget 1H [T0-72h, T0+48h] audits
│   │   └── vision_annotations.json          # 284 real TradingView chart CV extractions
│   ├── constitutional_checkpoint.json       # Active generation parameters & corridors
│   ├── live_shadow_snapshot.json            # Real-time Phase 5 Bitget USDT-FUTURES scan
│   ├── paper_ledger.json                    # Stateful Virtual Paper Exchange ledger ($1,000 base)
│   ├── self_improvement_journal.json        # FAJ1 SHA-256 hash-chained AI self-improvement log
│   ├── self_monitor_state.json              # 6-probe SelfMonitoringWatchdog & LatchHealer state
│   └── shadow_lead_time_log.json            # Phase 6.1 lead-time parity log (median -16.5s)
├── docs/
│   ├── BEHAVIORAL-ANALYSIS.md               # Empirical profile & forensic discoveries
│   ├── MASTER-PLAN.md                       # Phases 1–6 roadmap & Phase 7 canary criteria
│   └── OPERATIONS-RUNBOOK.md                # VPS systemd, OpenLiteSpeed/CF, CLI & API runbook
├── scripts/
│   ├── extract_corpus_readonly.py           # Air-gapped read-only SQLite/JSONL extractor
│   ├── run_turing_benchmark.py              # Full Phases 1–6 Turing, Bayes & backtest CLI
│   ├── run_shadow_daemon.py                 # Single-pass Bitget public-REST shadow scanner
│   ├── run_paper_trader.py                  # Virtual Paper Exchange (historical, live-step, daemon)
│   ├── run_self_improver.py                 # Watchdog + 4-stage AI Self-Improver CLI
│   └── run_web_ui.py                        # 7-tab Web Console & JSON API server (:18085)
├── src/
│   └── proteus/                             # Autonomous clone engine package
│       ├── domain/                          # Immutable domain models & value objects
│       ├── market/                          # Multi-TF lakehouse, 5000-bar miner & REST client
│       ├── compass/                         # BTC/ETH 1D macro regime gate
│       ├── geometry/                        # 3-tier 72h range & liquidity sweep detector
│       ├── vision/                          # RGB TradingView box extractor, 284-chart analyzer & renderer
│       ├── policy/                          # Rule policy + fitted 5097-bar Bayesian classifier
│       ├── params/                          # Directional SL (2.67%/2.17%), R:R & 10^k scaler
│       ├── fsm/                             # +1.0R breakeven & UTC 21:00+ bedtime trade FSM
│       ├── benchmark/                       # Behavioral Parity Score (BPS >= 0.85) harness
│       ├── replay/                          # 97-signal & 784-message empirical replay engine
│       ├── backtest/                        # 97-setup backtester + real-candle whipsaw audit
│       ├── shadow/                          # Live Bitget shadow scanner & lead-time comparator
│       ├── paper/                           # Virtual Paper Exchange (fees + 3-slot eviction)
│       ├── constitution/                    # ConstitutionalIdentityGuard & BoundedSelfCorrector
│       ├── monitor/                         # 6-probe SelfMonitoringWatchdog & LatchHealer
│       ├── evolver/                         # 4-stage AI-Agent Self-Improver & SHA-256 journal
│       ├── web/                             # 7-tab institutional HTML/JS console & REST API
│       └── engine.py                        # End-to-end pipeline orchestrator
├── tests/
│   └── test_proteus_engine.py               # 21-test invariant, CV, Bayes, audit, paper & evolver suite
├── AGENTS.md                                # Mandatory anti-drift rules for AI coding agents
├── ARCHITECTURE.md                          # Complete system topology & module contracts
├── IDENTITY.md                              # Immutable project identity & self-correction charter
├── pyproject.toml
├── README.md
└── .gitignore
```
