# Project Proteus — Constitutional Identity & Anti-Drift Charter

> **This document is the immutable constitution of `learnernoearner-distillation-engine`.**  
> Every human contributor, autonomous agent, and self-correction loop MUST obey this charter. Any code change or parameter update that violates these pillars is rejected by `proteus.constitution.ConstitutionalIdentityGuard`.

---

## 1. Core Identity: What This Project Is

**Project Proteus** has one—and only one—mission:
To be an **air-gapped, 1:1 cognitive and behavioral clone of human discretionary crypto trader `@learnernoearner`**, continuamente improving its fidelity through **bounded self-correction** while remaining anchored to his exact mental model.

We do **not** curve-fit arbitrary indicators to historical noise. We model the human trader's actual cognitive mechanics:
1. **Macro Compass Separation**: `BTC` and `ETH` are never traded directly; their 1D structure acts strictly as the macro regime gate (`BULLISH_EXPANSION`, `RANGE_BOUND`, `BREAKDOWN`) for high-beta perpetuals (`WLD`, `PUMP`, `ENA`, `ZEC`, `INJ`, `PENGU`, `MAGIC`, `NEAR`, `GRASS`, `PEPE`, `SNDK`, `TRUMP`).
2. **3-Tier Horizontal Range Perception**: Markets are navigated via 72-hour horizontal `Range High` (supply), `50% Mid Range` (equilibrium confirmation pivot), and `Range Low` (demand) levels—plus session liquidity wick sweeps (`wick_ratio >= 0.35`) and visual chart bounding boxes (`IoU >= 0.80`).
3. **Abstention as Primary Alpha**: When price floats in interior "no-man's land" between structural tiers, the engine **does nothing** ($P(\text{ABSTAIN}) \ge 0.85$). Over $85\%\text{–}98\%$ of intraday bars are rejected.
4. **Directional & Risk Asymmetry**:
   - **80.4% Long vs. 19.6% Short** structural bias (Short admission requires strictly higher conviction: $\theta_{\text{Short}} \ge \theta_{\text{Long}} + 0.15$).
   - **Tighter Short Stops vs. Wider Long Stops**: Shorts anchor tighter above Range-High wicks (**~2.17% median SL**, **~4.46R TP**); Longs anchor below 15m swing lows (**~2.67% median SL**, **~4.87R TP**).
   - **Single Structural Destination**: 92.8% of setups target a single opposing range boundary—never 5-tier retail scalp ladders.
5. **The 2-Hour Coupled Impulse FSM & Circadian Derisking**:
   - At the **~2.0-hour impulse mark** (8 bars on 15m, $+1.0R \text{ to } +1.5R$), the engine migrates Stop-Loss to Entry (`sl to entry` at median `119.1m`) and books $50\%$ partial profit (`tp1 booked` at median `123.6m`). This rescues **61.7% of $+1.0R$ impulses** from 48-hour whipsaw reversals and collapses Max Drawdown from `15.14R` to `2.00R`.
   - At **UTC 21:00–23:59 (Bedtime Window)**, unmonitored profitable trades are derisked before sleep.
   - At **3/3 active portfolio slots**, stalled trades ($-0.15R \le \text{unrealized\_r} \le +0.35R$) are evicted when a higher-conviction setup arrives.

---

## 2. Anti-Identity: What This Project Will NEVER Become

The following mutations are **permanently forbidden** (`IdentityDriftError`):

| Forbidden Drift | Why It Violates Identity | Machine Enforcement |
| :--- | :--- | :--- |
| **1. Lagging Retail Indicator Bot** (`RSI`, `MACD`, `EMA cross`, `Bollinger`, `Stochastic`, `Ichimoku`, `ADX`) | `@learnernoearner` never uses lagging oscillators. Adding them turns Proteus into a generic retail TA bot. | `ConstitutionalIdentityGuard.verify_codebase_purity()` scans AST/source and blocks forbidden indicator symbols. |
| **2. High-Frequency Scalper / Over-Trader** | Lowering abstention thresholds to force trades in "no-man's land" destroys the 10.08 Profit Factor. | `abstain_prob_no_mans_land >= 0.85` and `abstention_accuracy >= 0.95` hard floors. |
| **3. Naive Set-and-Forget Bot** | Disabling the $+1.0R$ `SL_TO_ENTRY` / `TP1` 2-hour FSM causes a `68.0%` loss rate and `15.14R` drawdown. | `breakeven_trigger_r` locked to $[0.80R, 1.35R]$; FSM transitions mandatory. |
| **4. Blind Copy-Trading Relay** | `fatty-multi-exchange-trader` already copy-trades Telegram messages. Proteus is an **independent cognitive decision engine** that detects setups from raw market structure *before* Telegram posts ($\Delta t \le 0\text{s}$). | Evaluated by `ShadowLeadTimeComparator` ($\Delta t \le 0\text{s}$) and `BehavioralParityBenchmark` ($BPS \ge 0.85$). |
| **5. Coupled Live Production Bot** | Proteus must never hold live Bitget API keys, HMAC secrets, or `fatty_trader` write sockets. | `ProteusDistillationEngine.verify_air_gap()` raises `AirGapSecurityError`. |

---

## 3. How Self-Correction & Fine-Tuning Work Without Losing Identity

Project Proteus is designed to **improve continuously over time** via `proteus.constitution.BoundedSelfCorrector`:

$$\theta_{t+1} = \operatorname{clip}\!\Big((1 - \alpha)\,\theta_{\text{anchor}} + \alpha\,\hat{\theta}_{\text{observed}},\; \theta_{\min},\; \theta_{\max}\Big)$$

1. **Prior-Anchored Bayesian Shrinkage**:
   - Every tunable parameter $\theta$ is tethered to its empirical **Constitutional Anchor** $\theta_{\text{anchor}}$ with a bounded learning rate $\alpha \in [0.05, 0.25]$. New observations fine-tune the engine smoothly without erasing historical wisdom.
2. **Hard Constitutional Corridors ($[\theta_{\min}, \theta_{\max}]$)**:
   - No matter how extreme a recent market regime is, no parameter can ever be tuned outside its constitutional corridor:
     - `long_conviction_threshold`: $[0.60, 0.75]$ (Anchor: $0.65$)
     - `short_conviction_threshold`: $[0.80, 0.93]$ (Anchor: $0.85$, invariant $\theta_{\text{Short}} - \theta_{\text{Long}} \ge 0.15$)
     - `no_mans_land_abstain_prob`: $[0.85, 0.98]$ (Anchor: $0.92$)
     - `median_sl_long_pct`: $[0.0180, 0.0360]$ (Anchor: $0.0267$)
     - `median_sl_short_pct`: $[0.0140, 0.0300]$ (Anchor: $0.0217$, invariant $\text{SL}_{\text{Short}} < \text{SL}_{\text{Long}}$)
     - `median_rr_long`: $[3.50, 6.50]$ (Anchor: $4.87$)
     - `median_rr_short`: $[3.20, 5.80]$ (Anchor: $4.46$)
     - `breakeven_trigger_r`: $[0.85, 1.25]$ (Anchor: $1.00$)
3. **Automatic Turing Rollback Gate**:
   - Every candidate fine-tune must pass `BehavioralParityBenchmark` ($BPS \ge 0.85$, Abstention $\ge 95\%$, Profit Factor $\ge 4.0$, Max Drawdown $\le 3.5R$). If a candidate update fails any gate, `BoundedSelfCorrector` **automatically rejects the update and rolls back** to the last verified constitutional state.
