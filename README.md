# Project Proteus: Trader Distillation Engine (`@learnernoearner`)

> **Live Web Console**: [`https://engine.warga-digital.com`](https://engine.warga-digital.com) (`127.0.0.1:18085` · 24/7 Systemd Daemon)  
> **Companion Copy-Trader**: [`https://trade.warga-digital.com`](https://trade.warga-digital.com) (`fatty-multi-exchange-trader` · `:18081`)  
> **Isolation Charter**: 100% air-gapped cognitive clone. Zero live Bitget API keys, zero HMAC/3DES secrets, zero production DB write sockets.

---

## 🎯 Mission & Paradigm

**Project Proteus** reverse-engineers the implicit market heuristics, 3-tier horizontal range perception, visual chart saliency, and intraday risk management of discretionary crypto trader `@learnernoearner` into an autonomous, self-monitoring, self-improving decision engine.

Unlike reactive copy-trading (which suffers $6\text{–}28\text{s}$ human screenshot/typing lag and **53.8% survivorship silence** on unannounced stop-outs) or naive retail indicator bots (which curve-fit lagging oscillators like RSI/MACD), Project Proteus models the human as a **Bayesian structural range & liquidity agent** governed by four empirical laws:
1. **Macro Compass Separation (`proteus.compass`)**: `BTC` and `ETH` are never traded directly; their 1D candles gate directional admission across the **45 perpetuals `@learnernoearner` actually traded** in the **95-setup** corpus that remain listed on Bitget USDT-FUTURES (full list in `src/proteus/market/__init__.py`; `SAGA`, `BONK`, `FLOW` are excluded because Bitget delisted them).
2. **72-Hour 3-Tier Range & Abstention First (`proteus.geometry`, `proteus.policy`)**: Price is mapped against 72h `Range High`, `50% Mid Range`, and `Range Low`. Over **85%–98%** of intraday bars floating in interior "no-man's land" are dropped ($P(\text{ABSTAIN}) = 0.92$).
3. **Directional Conviction & Stop/Target Asymmetry (`proteus.params`)**:
   - **80.0% LONG (76)** ($\theta_{\text{Long}} \ge 0.65$, **2.68% median SL**, **4.89R median TP**) vs. **20.0% SHORT (19)** ($\theta_{\text{Short}} \ge 0.85$, **2.17% median SL**, **4.46R median TP**).
   - Structural retests emit **`LIMIT`** orders (`2.0 bps` Maker fee); liquidity sweep reclaims emit **`MARKET`** orders (`6.0 bps` Taker fee).
4. **The 2-Hour Coupled Impulse FSM (`proteus.fsm`)**:
   - Real Bitget 1H candle forensics (`86` resolved setups) proved that while **54.7% ($47/86$)** reach $+1.0R$ before SL, **61.7% ($29/47$) of those $+1.0R$ winners reverse to the original SL within 48 hours**.
   - In a conservative 1H re-simulation (`docs/AUDIT-2026-11-10.md`), migrating `SL → Entry` at **$+1.0R$** and booking $50\%$ at **`TP1`** reduces max drawdown from **18.62R to 10.50R** but does **not** turn a profit (`PF 0.82` vs `0.96`). The earlier `PF 10.08` / `$2,938.51` figures were produced by keyword→fixed-R and SHA-256 outcome mappings; they are retired.

---

## 📚 Core Documentation Index

- **[Constitutional Identity Charter](IDENTITY.md)**: Immutable anti-drift manifesto, 7 cognitive pillars, 5 forbidden anti-identities, and hard self-correction corridors.
- **[AI Agent Instructions](AGENTS.md)**: Mandatory startup rules for coding agents operating in this repository.
- **[System Architecture & Module Contracts](ARCHITECTURE.md)**: End-to-end 12-subpackage topology, domain dataclasses, and hard invariant guarantees.
- **[Empirical Behavioral & Forensic Analysis](docs/BEHAVIORAL-ANALYSIS.md)**: Complete quantitative & qualitative profile across 784 Telegram messages, 95 canonical setups, 47 management actions, 86 Bitget 1H candle trajectories, and 284 TradingView chart screenshots.
- **[Engineering Master Plan (Phases 1–6 Implemented, Unvalidated)](docs/MASTER-PLAN.md)**: Implemented architecture, the unmeasured Behavioral Parity Scorecard, and Phase 7 Canary Graduation criteria.
- **[Operations & Deployment Runbook](docs/OPERATIONS-RUNBOOK.md)**: Production runbook for `https://engine.warga-digital.com`, `systemd` services, OpenLiteSpeed + Cloudflare routing, REST API endpoints, CLI modes, and Operator Action Gates.

---

## 📊 Empirical Status (2026-11-10)

> **Validation status: UNVALIDATED.** BPS is `None` while independent direction, vision, and lead-time labels are missing. The numbers below are what the corpus actually supports.

| Dimension | Scope | Current result | Status |
| :--- | :--- | ---: | :--- |
| **Behavioral Parity Score ($BPS$)** | 784 msgs · 95 setups · 47 updates | **Unmeasured** | `directional`, `spatial`, `abstain`, `timing` missing |
| **Leak-free Bayesian Policy** | 5,000 negatives + 91 signals | **98.56% abstain / 4.4% recall** | No longer tautological |
| **Candle-Driven Backtest** | 91 resolvable setups · 1H · conservative · net fees | **Naive −3.03R / PF 0.96 / DD 18.62R** vs **FSM −7.76R / PF 0.82 / DD 10.50R** | FSM cuts DD, not profitable |
| **Shadow Lead-Time Parity ($\Delta t$)** | 0 paired detections | **Unmeasured** | Needs logged scan timestamps |
| **284-Chart Vision Pass** | 216 Light (76.1%) · 68 Dark (23.9%) | **238 legacy detector boxes** | No human labels; IoU unmeasured |
| **$1,000 Paper Sim (Net of Fees)** | `$20/1R` risk · 91 setups | **$844.80 (−15.52%)** vs naive **$939.40** | Honest baseline |
| **Constitutional Codebase Purity** | All `src/proteus/` Python modules | **31/31 files pure** | Zero retail oscillators |
| **Automated Test Suite (`pytest`)** | Invariant, CV, replay, rate-limit, stream, regression | **41/41 passed** | `100% pass` |

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
│   │   ├── canonical_signals.json           # 95 canonical trade setups
│   │   ├── management_updates.json          # 47 in-flight management actions
│   │   ├── telegram_messages.json           # 784 raw Telegram messages
│   │   ├── signal_candle_trajectories.json  # 86 real Bitget 1H [T0-72h, T0+48h] audits
│   │   └── vision_annotations.json          # 284 real TradingView chart CV extractions
│   ├── constitutional_checkpoint.json       # Active generation parameters & corridors
│   ├── live_shadow_snapshot.json            # Real-time Phase 5 Bitget USDT-FUTURES scan
│   ├── paper_ledger.json                    # Stateful Virtual Paper Exchange ledger ($1,000 base)
│   ├── self_improvement_journal.json        # FAJ1 SHA-256 hash-chained AI self-improvement log
│   ├── self_monitor_state.json              # 6-probe SelfMonitoringWatchdog & LatchHealer state
│   └── shadow_lead_time_log.json            # Phase 6.1 lead-time log (unmeasured until scans are logged)
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
│       ├── market/                          # Multi-TF lakehouse, rate-limited REST + websocket candle stream
│       ├── compass/                         # BTC/ETH 1D macro regime gate
│       ├── geometry/                        # 3-tier 72h range & liquidity sweep detector
│       ├── vision/                          # RGB TradingView box extractor, 284-chart analyzer & renderer
│       ├── policy/                          # Rule policy + fitted 5,091-bar Bayesian classifier
│       ├── params/                          # Directional SL (2.68%/2.17%), R:R & 10^k scaler
│       ├── fsm/                             # +1.0R breakeven & UTC 21:00+ bedtime trade FSM
│       ├── benchmark/                       # Behavioral Parity Score harness (refuses unmeasured components)
│       ├── replay/                          # 95-signal & 784-message empirical replay engine
│       ├── backtest/                        # candle-driven backtester + real-candle whipsaw audit
│       ├── shadow/                          # Live Bitget shadow scanner & lead-time comparator
│       ├── paper/                           # Virtual Paper Exchange (fees + 3-slot eviction)
│       ├── constitution/                    # ConstitutionalIdentityGuard & BoundedSelfCorrector
│       ├── monitor/                         # 6-probe SelfMonitoringWatchdog & LatchHealer
│       ├── evolver/                         # 4-stage AI-Agent Self-Improver & SHA-256 journal
│       ├── web/                             # 7-tab institutional HTML/JS console & REST API
│       └── engine.py                        # End-to-end pipeline orchestrator
├── tests/
│   ├── test_proteus_engine.py               # 23-test invariant, CV, Bayes, audit, paper & evolver suite
│   ├── test_bitget_client.py                # 4-test rate-limit, retry, cache & relay-fallback suite
│   └── test_bitget_ws.py                    # 9-test candle-shard, push-upsert, staleness, close-trigger suite
├── AGENTS.md                                # Mandatory anti-drift rules for AI coding agents
├── ARCHITECTURE.md                          # Complete system topology & module contracts
├── IDENTITY.md                              # Immutable project identity & self-correction charter
├── pyproject.toml
├── README.md
└── .gitignore
```
