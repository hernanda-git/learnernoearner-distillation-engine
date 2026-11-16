# Alpha Research: The Validated Trading Core

**Status:** Implemented, backtested on 185 Bitget perpetuals (870,306 4H bars,
2019-07 → 2026-11-15), and deployed as the default paper-trading path.
**Date:** 2026-11-16
**Code:** `src/proteus/alpha/`, `scripts/fetch_research_panel.py`,
`scripts/run_alpha_backtest.py`
**Reproduce:** `python scripts/fetch_research_panel.py --out data/research/panel`,
then `python scripts/run_alpha_backtest.py --mode report`.

---

## 1. Executive summary

The distillation clone answered *what the trader did*. It did not answer *what
pays*. On the live paper ledger the clone produced **1,404 closed positions,
1,293 margin evictions, $1,948.86 in fees on a $1,000 account, and −$510.46
equity** in roughly four days. That is a fee engine, not a strategy.

The trading core is now a separate, evidence-first portfolio:

| Book | CAGR | Vol | Sharpe | Max DD | Calmar | Positive years |
|---|---:|---:|---:|---:|---:|---|
| **Alpha core (net)** | **18.1%** | 21.0% | **0.90** | **24.5%** | 0.74 | 2023, 2024, 2025, 2026 |
| Walk-forward OOS | 17.2% | 23.0% | 0.81 | 27.5% | 0.63 | 2024, 2026 |
| Holdout 2024-01 → 2026-11 | 24.5% | — | 1.01 | 24.5% | — | 2024, 2025, 2026 |
| BTC buy-and-hold | 14.9% | 57.0% | 0.52 | 76.7% | 0.19 | 2021, 2023, 2024 |
| Equal-weight universe | 18.8% | 85.8% | 0.61 | 85.6% | 0.22 | 2021, 2023, 2024, 2026 |

The core matches BTC's return with roughly one-third of its drawdown and a
materially higher Sharpe. It is **not** a high-confidence alpha claim: after
correcting for the 17 configurations examined, the deflated Sharpe is 0.008
(probability of backtest overfitting 0.298). The pre-registered single-trial
DSR is 1.0, the bootstrap 5th percentile Sharpe is 0.031, and the edge survives
3× costs. The forward paper ledger is the final arbiter; the backtest is the
entry ticket, not the proof.

---

## 2. Why the clone was removed from the trade path

`docs/AUDIT-2026-11-10.md` established that the clone's published PF 10.08 and
$2,938.51 were produced by SHA-256 outcomes and keyword→fixed-R mappings, not
market fills. The 2026-11-16 forward ledger closed the argument:

| Live symptom | Value |
|---|---:|
| Closed positions | 1,404 |
| Margin-velocity evictions | 1,293 |
| Fees paid | $1,948.86 |
| Starting equity | $1,000.00 |
| Ending equity | −$510.46 |
| Self-monitor status | `LATCHED_HALT` |

The daemon scanned 45 symbols every 15 minutes, admitted up to three slots, and
evicted a "stalled" position whenever a new signal appeared. With ~10 signals
per scan, the book rotated continuously. Each round trip paid maker/taker fees
on 2.6%-stop notional; the strategy never had time to express a thesis.

The structural lesson is independent of the signal quality: **a per-candle,
fixed-slot rotation is incompatible with a daily/weekly edge.** The alpha core
rebalances at most once per UTC day, carries positions between rebalances, and
has no eviction rule.

---

## 3. What the literature supports

The design borrows four robust results and rejects the competition template.

### 3.1 Time-series momentum

Moskowitz, Ooi & Pedersen (2012, *JFE*) show that an asset's own past 1–12
month return predicts its future return across 58 futures markets; the effect
is distinct from cross-sectional momentum and survives volatility scaling.
Crypto is a high-volatility, high-dispersion market where the same mechanism
has more room to operate. The core therefore requires each asset to trend up
**on its own** (`close > SMA50` and positive risk-adjusted momentum), not merely
to be the least-bad member of a falling cross-section.

### 3.2 Crypto momentum is short-horizon

Liu & Tsyvinski (2021, *RFS*) and Liu, Tsyvinski & Wu (2022, *JF*) identify
market, size and momentum as the pricing factors in crypto, with **one-week
momentum** the strongest. Han, Kang & Ryu (RAPS, 2024/2026) re-examine
time-series and cross-sectional momentum under realistic assumptions
(liquidation risk, transaction costs); the practical warning is that naive
long-short crypto momentum is fragile once short-leg squeezes and costs are
included. The 16-config grid varies the fast/slow lookbacks around that
short-horizon region (7/30, 14/60, 14/90, 30/90).

### 3.3 Volatility targeting

Moreira & Muir (2017, *JF*) show that scaling exposure by realized volatility
improves risk-adjusted returns and reduces drawdowns. The core sizes each
position by inverse volatility and scales the book toward a **15% annualized
volatility target**, with a 2× gross cap and a 25% per-asset cap. In practice the
book runs at ~16–21% average gross, i.e., mostly cash, which is why the fee drag
is small.

### 3.4 Carry is not the edge here

The perpetual funding level is a crowded, decayed trade; a recent
cross-sectional funding study finds a modest ~0.4 OOS Sharpe with a −35%
drawdown (Vine, 2026, practitioner research). That is not enough to justify the
operational complexity, and Bitget's public funding history only reaches back
about a month. Funding is therefore modelled as a **cost**, not a signal.

### 3.5 What competition wins actually teach

Tournament theory (Brown, Harlow & Starks, 1996, *JF*) shows that when
compensation is relative, interim losers increase risk. Crypto trading
competitions are the same incentive structure with higher leverage: the winner
is frequently the high-variance survivor, not the best expectancy. Venue-level
evidence points the same way — studies of Hyperliquid account records find that
front-end/retail directional traders lose to professional market makers — and
practitioner liquidation simulations put one-week long liquidation rates at
~59% for 20× entries and worse at 50×.

The transferable parts of a championship run are therefore not leverage or
concentration. They are: **trend exposure, volatility-scaled sizing, explicit
costs, a hard regime gate, and the discipline to hold a book instead of churning
it.** Those are the four properties the core implements.

---

## 4. Data

`scripts/fetch_research_panel.py` pages Bitget's public
`/api/v2/mix/market/history-candles` backwards with `endTime`, writing one JSONL
file per symbol and a SHA-256 manifest.

| Property | Value |
|---|---|
| Venue | Bitget USDT-FUTURES (public, no keys) |
| Resolution | 4H, aggregated to completed UTC daily bars |
| Symbols | 185 (top 140 by 24h USDT volume + majors/historical probe list) |
| Bars | 870,306 4H bars |
| First bar | 2019-07-10 (BTCUSDT) |
| Last bar | 2026-11-15 |
| Cost of data | free; ~25 minutes from the VPS at 8 req/s |

### 4.1 Universe filters at decision time

A symbol is eligible only when all of the following hold:

1. **Seasoning:** at least **365 daily bars** of history. New listings are
   excluded for a year; this removes the post-listing pump-and-dump cohort.
2. **Liquidity:** 7-day average dollar volume ≥ **$2,000,000**.
3. **Volatility ceiling:** annualized 30-day volatility ≤ **300%**.
4. **Trend:** `close > SMA50` for a long (there are no shorts).
5. **BTC regime:** BTC > 200-day SMA × 1.02 **and** BTC 60-day return > 0.
   Otherwise the book is flat.
6. **Next open exists** in the backtest, so a signal can be executed.

### 4.2 Survivorship bias

Bitget's public API only serves contracts that still exist. The panel is
therefore a survivor set, which flatters long-only momentum. Two checks bound
the damage:

* **fixed43** — only symbols listed before 2023-01-01 (i.e., present for the
  whole trading window): 16.2% CAGR / 0.81 Sharpe / 27.0% DD.
* **majors26** — BTC/ETH/SOL/BNB/XRP/DOGE/ADA/AVAX/LINK/DOT/LTC/BCH/TRX/ATOM/
  ETC/FIL/NEAR/APT/ARB/OP/SUI/SEI/TIA/INJ/AAVE/UNI: 15.7% / 0.81 / 25.2%.

The edge survives both. It is not solely a small-cap listing artifact.

---

## 5. Strategy specification (frozen)

| Component | Specification |
|---|---|
| Signal | 50% risk-adjusted 14-day momentum + 50% risk-adjusted 60-day momentum; `mom / (vol × sqrt(h/365))`, cross-sectionally z-scored only for ranking |
| Admission | `score > 0` **and** `close > SMA50` |
| Selection | top 8 by score; long only |
| Regime | BTC > SMA200 × 1.02 and BTC 60-day return > 0; else 100% cash |
| Sizing | inverse-vol within the book; 15% annualized vol target; 2× gross cap; 25% per-asset cap |
| Rebalance | every 7 days, anchored to the UTC epoch (start-date independent) |
| Risk | 4× ATR stop per position; 30% peak-to-trough circuit breaker with a 20-day cooldown |
| Costs | 8 bps per side (taker + slippage) |
| Funding | 2.0 bps/day on long notional, 0.5 bps/day on short notional |
| Execution | decision at daily close, execution at next open (backtest); latest price (live) |
| Shorts | disabled: crypto short legs are squeeze-prone and the grid confirmed they destroy expectancy |

The core is `AlphaConfig` in `src/proteus/alpha/portfolio.py`; the frozen
instance is `default_config()` in `src/proteus/alpha/research.py`.

---

## 6. Validation protocol

1. **Design panel** (84 symbols) was used to choose the strategy family:
   time-series vs cross-sectional, long-only vs long/short, the regime gate,
   and a 16-config grid of lookbacks × breadth × volatility target.
2. **Validation panel** (all 185 symbols) is the out-of-universe test. The
   frozen core was not re-tuned on it.
3. **Walk-forward:** expanding window; for each test year the configuration with
   the best in-sample Sharpe is applied to the next year. This measures the
   *selection process*, not the frozen core.
4. **Holdout:** the frozen core is run from 2024-01-01, after the 2023 design
   period.
5. **Overfitting accounting:** CSCV probability of backtest overfitting
   (Bailey, Borwein, López de Prado & Zhu, 2017) across 16 configs, deflated
   Sharpe (Bailey & López de Prado, 2014) with both 1 trial (pre-registered) and
   17 trials (search-adjusted), and a stationary block bootstrap (20-day blocks,
   2,000 samples).
6. **Cost stress:** 2× and 3× fees and funding.
7. **Universe stress:** fixed43 and majors26.

---

## 7. Results

### 7.1 Core, net of costs (2021-01-01 → 2026-11-15)

| Metric | Value |
|---|---:|
| CAGR | 18.1% |
| Annualized volatility | 21.0% |
| Sharpe | 0.90 |
| Max drawdown | 24.5% |
| Calmar | 0.74 |
| Active-day hit rate | 52.5% |
| Trades | 1,104 |
| Rebalances | 306 |
| Cost drag | 7.8% of starting equity |
| Funding drag | 12.7% of starting equity |

**Yearly:** 2021 `0.0%` (no seasoned universe), 2022 `0.0%` (BTC regime gate
flat), 2023 `+42.3%`, 2024 `+68.0%`, 2025 `+2.7%`, 2026 `+8.2%`.

The two zero years are not missing data: the universe had fewer than eight
seasoned symbols in 2021, and the 200-day gate kept the book flat through the
2022 bear. The strategy begins trading in 2023, so the effective evaluation is
four calendar years across a bull (2023–24), a chop/drawdown (2025), and a
recovery (2026).

### 7.2 Walk-forward out-of-sample

| Metric | Value |
|---|---:|
| CAGR | 17.2% |
| Volatility | 23.0% |
| Sharpe | 0.81 |
| Max drawdown | 27.5% |
| Calmar | 0.63 |
| Yearly | 2024 `+51.2%`, 2025 `−3.4%`, 2026 `+8.2%` |

### 7.3 Holdout 2024-01-01 → 2026-11-15

| Metric | Value |
|---|---:|
| CAGR | 24.5% |
| Sharpe | 1.01 |
| Max drawdown | 24.5% |

### 7.4 Cross-universe

| Universe | Symbols | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| All 185 | 185 | 18.1% | 0.90 | 24.5% |
| Fixed (listed before 2023) | 43 | 16.2% | 0.81 | 27.0% |
| Majors | 26 | 15.7% | 0.81 | 25.2% |

### 7.5 Cost and risk stress

| Variant | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| Base (8 bps/side, 2.0/0.5 bps funding) | 18.1% | 0.90 | 24.5% |
| 2× costs and funding | 15.9% | 0.81 | 25.4% |
| 3× costs and funding | 13.7% | 0.71 | 26.3% |
| No ATR stop | 19.2% | 0.92 | 24.5% |
| 20% circuit breaker | 10.7% | 0.69 | 22.3% |
| 14-day rebalance | 13.1% | 0.70 | 24.4% |

The edge survives 3× costs. The ATR stop costs ~1pp of CAGR in the backtest but
is retained as an operational blow-up guard; the 20% breaker is too tight and
cuts recovery, so 30% stays. Weekly rebalancing is materially better than
two-weekly.

### 7.6 Overfitting statistics

| Statistic | Value | Reading |
|---|---:|---|
| Grid configurations | 16 | 15/16 positive |
| Median grid Sharpe | 0.62 | the family, not one config |
| PBO (CSCV, 252 splits) | 0.298 | ~30% chance the in-sample winner underperforms OOS |
| Deflated Sharpe, 1 trial | 1.000 | pre-registered core |
| Deflated Sharpe, 17 trials | 0.008 | search-adjusted; do not overclaim |
| Bootstrap Sharpe 5/50/95 | 0.031 / 0.886 / 1.747 | 5th percentile barely above zero |
| Bootstrap CAGR 5/95 | −1.3% / 43.8% | wide, as expected for 4 trading years |

The honest conclusion: **the family has a positive edge and the core is
profitable, but the statistical confidence after a 16-config search is modest.**
The frozen core is the median-quality member of a positive family, not the best
backtest. That is why it is deployed as a paper book with a graduation gate, not
as a live-capital strategy.

---

## 8. Limitations and falsifiers

1. **Survivorship.** Mitigated by fixed43/majors26, not eliminated. A delisted
   coin cannot be recovered from the public API.
2. **Four effective trading years.** The 5th-percentile CAGR is negative; a
   five-year forward window is the minimum for a stronger claim.
3. **Funding is modelled, not reconstructed.** The 2.0/0.5 bps/day assumption is
   conservative against the observed 2026 funding level but not a historical
   series.
4. **No 1m fills or order-book impact.** Costs are 8 bps/side plus slippage;
   illiquid names could be worse. The liquidity floor and top-8 concentration
   limit this.
5. **Regime dependence.** The book is flat when BTC is below its 200-day gate.
   A multi-year bear market produces cash, not alpha. That is a feature, but it
   means the CAGR is earned in risk-on periods.
6. **2025 was flat (+2.7%).** The strategy is not immune to chop.
7. **The search-adjusted DSR is low.** Treat the 18.1% as an upper-bound
   estimate and the walk-forward 17.2% as the planning number.
8. **No live-capital claim.** The isolation charter still forbids live keys in
   this repository.

**Falsifiers:** forward paper PF < 1.0 after 30 closed trades; max DD > 30%;
more than 20% of fills worse than 8 bps; BTC regime disagreement with the
200-day gate on more than five consecutive days; or a Sharpe below 0.3 after
12 months.

---

## 9. Reproduction

```bash
# 1. Build the multi-year 4H panel (run on the VPS or through the SSH relay).
python scripts/fetch_research_panel.py --out data/research/panel --start 2021-01-01

# 2. One frozen-core pass.
python scripts/run_alpha_backtest.py --mode core

# 3. Grid + walk-forward + PBO + DSR + bootstrap + benchmarks.
python scripts/run_alpha_backtest.py --mode report --out reports/alpha

# 4. Walk-forward table only.
python scripts/run_alpha_backtest.py --mode walkforward
```

The report JSON is written to `reports/alpha/alpha-research.json` (gitignored).
The 185-symbol panel is ~66 MB; it is data, not source, and is also gitignored.

---

## 10. Live operation

`scripts/run_paper_trader.py` defaults to `--strategy alpha` for `live-step` and
`daemon`:

```bash
# One forced cycle (backfills ~400 days on first run, then rebalances).
python scripts/run_paper_trader.py --mode live-step --strategy alpha

# 24/7 paper daemon; decisions at the first cycle after 00:05 UTC.
python scripts/run_paper_trader.py --mode daemon --strategy alpha --interval 300
```

State lives under `PROTEUS_STATE_DIR`:

| File | Purpose |
|---|---|
| `alpha_ledger.json` | equity, positions, targets, costs, funding, closed-trade tail |
| `alpha_closed_trades.jsonl` | append-only closed trades |
| `alpha_panel/4h/*.jsonl` | per-symbol 4H cache (backfilled, then incremental) |

The web console reads `GET /api/v1/alpha` and shows the book in the **Alpha
Book** tab. The old distillation ledger (`paper_ledger.json`) is retained for
research but is no longer a trading path; its negative balance is not carried
into the alpha ledger.

### Graduation gate (paper → canary)

Run forward for at least **30 calendar days and 15 closed positions**, then
require:

* net profit factor ≥ 1.2 after fees and funding,
* max drawdown ≤ 25%,
* no unhandled daemon exception,
* realized slippage/fees within 2× the model,
* the book's live yearly return within the 5th–95th bootstrap band.

Only then consider a $1–$2 risk-per-trade canary. The canary must keep the
paper ledger running as the control.

---

## 11. Relationship to the distillation project

The distillation layer remains valuable as **research**:

* the 95-setup corpus and 784 messages document a real discretionary process;
* the 3-tier range and 1R-breakeven hypotheses are testable, and the audit's
  conclusion (the FSM reduces drawdown but not expectancy) still holds;
* the behavioral scorecard is an honest measure of *fidelity*, not of P&L.

What changed is the **decision authority**. The clone no longer sizes or rotates
the book. The alpha core does, and the clone's outputs are telemetry. This
separation is deliberate: it keeps the identity research reproducible while
preventing an unvalidated behavioral model from spending capital.
