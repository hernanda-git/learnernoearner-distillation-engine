# Agent Instructions — `learnernoearner-distillation-engine` (Project Proteus)

MUST read and obey `IDENTITY.md` before modifying any code, model weights, or documentation in this repository.

## Non-Negotiable Identity Rules

1. **Purpose**: This repository is **Project Proteus** — an air-gapped, 1:1 cognitive and behavioral distillation clone of discretionary trader `@learnernoearner`. It is **not** a generic TA indicator bot, **not** a high-frequency scalper, and **not** a copy-trading execution relay.
2. **Air-Gap Invariant**:
   - NEVER add live Bitget API keys (`BITGET_API_KEY`, `BITGET_SECRET`, `TRIPLEDES`) or write connections to the production VPS (`fatty-multi-exchange-trader`).
   - All market scans use zero-credential public REST data; all execution simulations run in `VirtualPaperExchange` (`proteus.paper`).
3. **Cognitive Architecture Invariants**:
   - **Zero Lagging Indicators**: NEVER introduce `RSI`, `MACD`, `BollingerBands`, `Stochastic`, `Ichimoku`, `ADX`, or `EMA crossover` logic into `src/proteus/`. `ConstitutionalIdentityGuard.verify_codebase_purity()` will fail the test suite if forbidden indicator names appear.
   - **Macro Compass (`proteus.compass`)**: `BTC` and `ETH` are never traded directly; they act strictly as 1D regime filters.
   - **3-Tier Range & Visual Saliency (`proteus.geometry`, `proteus.vision`)**: Decisions are driven by 72h `Range High`, `50% Mid Range`, `Range Low`, session wick sweeps, and TradingView RGB box saliency ($\text{IoU} \ge 0.80$).
   - **Abstention & 80/20 Bias (`proteus.policy`)**: Maintain $\ge 95\%$ negative-space abstention accuracy and the asymmetric conviction gap ($\theta_{\text{Short}} - \theta_{\text{Long}} \ge 0.15$).
   - **Asymmetric Risk & 2-Hour Coupled FSM (`proteus.params`, `proteus.fsm`)**: Preserve tighter Short stops (~2.17% SL, ~4.46R TP) vs. Long stops (~2.67% SL, ~4.87R TP), the $+1.0R$ `SL_TO_ENTRY` + $50\%$ `TP1` 2-hour impulse lock, UTC 21:00+ bedtime derisking, and 3-slot margin velocity eviction.
4. **Bounded Self-Correction Only (`proteus.constitution`)**:
   - All parameter fine-tuning MUST flow through `BoundedSelfCorrector.propose_fine_tune()`, which enforces Constitutional Corridors and rolls back any update that drops Behavioral Parity Score ($BPS$) below `0.85`.
5. **Verification Gate**:
   - Before committing, ALWAYS run `pytest -v` and `python scripts/run_turing_benchmark.py`. All constitutional and Turing parity gates must pass 100%.
