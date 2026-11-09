# Operations & Deployment Runbook — Project Proteus (`engine.warga-digital.com`)

---

## 1. Production Deployment Topology (`46.202.155.192`)

| Resource | Value / Path on VPS (`srv691444.hstgr.cloud`) |
| :--- | :--- |
| **Public HTTPS Origin** | [`https://engine.warga-digital.com`](https://engine.warga-digital.com) |
| **Cloudflare DNS (`warga-digital.com`)** | Zone `e50fd82a7d0ce5d0076bb4f648ad9838` · Record ID `7226ab1b4b735bea3dd1d1d2f748e17a` (`A` → `46.202.155.192`, `proxied: true`) |
| **OpenLiteSpeed Vhost** | `/usr/local/lsws/conf/vhosts/engine.warga-digital.com/vhost.conf` (`proteus_engine_proxy` → `127.0.0.1:18085`, `respBuffer 0`) |
| **OpenLiteSpeed Listeners** | Mapped in `Default` (`*:80`), `SSL` (`*:443`), and `SSL IPv6` inside `/usr/local/lsws/conf/httpd_config.conf` |
| **Application Directory** | `/home/valarion/apps/learnernoearner-distillation-engine` |
| **Python Runtime** | `/home/valarion/.local/bin/python3.12` |
| **Web Console Systemd Unit** | `/etc/systemd/system/proteus-web.service` (`127.0.0.1:18085`, `Restart=always`) |
| **24/7 Paper Daemon Systemd Unit** | `/etc/systemd/system/proteus-paper-daemon.service` (`--mode daemon --interval 300`, `Restart=always`) |

---

## 2. Web Console Tabs & REST API Endpoints

### 2.1 Interactive Console Tabs (`https://engine.warga-digital.com`)
1. **Tab 1 — Live Shadow Radar & Paper Exchange**: Active Virtual Paper Ledger (`$1,000` base, `$20` risk/trade, max `3` slots), 72h 3-Tier Range Position gauges across all 45 Bitget-listed perpetuals, and Phase 6.1 Shadow Lead-Time Parity log ($\Delta t = -16.5\text{s}$).
2. **Tab 2 — 97-Setup Backtest & Real-Candle Whipsaw Audit**: Side-by-side comparison of Distilled Proteus FSM (`64.9%` win rate, `10.08` PF, `2.00R` Max DD) vs. Naive Set-and-Forget (`32.0%` win rate, `2.48` PF, `15.14R` Max DD) + 87-signal Bitget 1H candle forensic audit.
3. **Tab 3 — All 97 Canonical Signals & 48h MFE/MAE**: Searchable/filterable ledger of all 97 signals with 48h real Bitget Max Favorable Excursion ($R$), Max Adverse Excursion ($R$), minutes to $+1.0R$, minutes to SL, and verbatim Telegram text.
4. **Tab 4 — Behavioral Profile & 47 In-Flight Actions**: Directional SL/R:R quantile baselines, 784-message cognitive taxonomy, and all 47 in-flight management updates (`SL_TO_ENTRY`, `TP1_BOOKED`, `TP_BOOKED`, `CLOSE`).
5. **Tab 5 — Computer Vision Lab (284 TradingView Charts)**: Pixel-level RGB/HSV summary and 60-chart table showing Light/Dark theme classification, green TP boxes, red SL boxes, blue/purple S/R bands, and visual implied R:R.
6. **Tab 6 — Constitutional Guard & Self-Corrector**: All 10 Constitutional Corridors ($\theta_{\min}$, $\theta_{\text{anchor}}$, active value, $\theta_{\max}$) and the interactive Bounded Bayesian Self-Correction Simulator.
7. **Tab 7 — Self-Monitor Watchdog & AI Agent Evolver**: Live status of all 6 runtime probes (`LatchHealer`), 4-stage AI-Agent Self-Improvement trace (`TelemetryScout` → `AdversarialCritic` → `TuringVerifier` → `HashChainCommitter`), and the `FAJ1` SHA-256 hash-chained journal.

### 2.2 JSON REST Endpoints
- `GET /health` or `GET /health/telemetry` — Fast health, air-gap, constitutional purity (`26/26` files), and watchdog status check.
- `GET /api/v1/dashboard` — Full telemetry payload powering all 7 tabs.
- `POST /api/v1/scan` — Trigger an immediate Bitget public candle scan, step `VirtualPaperExchange`, and evaluate `SelfMonitoringWatchdog`.
- `POST /api/v1/self-correct` — Test a parameter proposal `{parameter, observed_value, learning_rate, candidate_bps}` through `BoundedSelfCorrector`.
- `POST /api/v1/evolve` — Trigger a full 4-stage `AgenticSelfImprover` cycle and append to `benchmarks/self_improvement_journal.json`.

### 2.3 Bitget Market-Data Rate-Limit Protection

`proteus.market.bitget.BitgetPublicMarketClient` is the single code path that reads Bitget candles. The exchange allows **20 requests/second per IP** on `/api/v2/mix/market/candles` and answers HTTP 429 beyond it.

| Guard | Default | Env override |
| :--- | :--- | :--- |
| Token-bucket limiter | 8 req/s | `BITGET_RATE_LIMIT_RPS` |
| Parallel fetch workers | 4 | `BITGET_MAX_WORKERS` |
| Retries (429 / 5xx / network) | 4 attempts, jittered exponential backoff, honours `Retry-After` | `BITGET_MAX_ATTEMPTS` |
| Per-request timeout | 6 s | `BITGET_TIMEOUT_SECONDS` |
| 429 cooldown after 3 consecutive hits | 5 s | — |
| Candle TTL cache | 60 s (15m/4H), 120 s (1D) | — |
| Scan universe override | `TRADABLE_UNIVERSE` (45 symbols) | `PROTEUS_SCAN_SYMBOLS=WLD,PEPE,...` |

A full 45-symbol cycle issues 92 candle requests (18×4H + 12×15m per symbol, plus 5×1D each for BTC/ETH). At 8 req/s that is ≈12 s and uses ~4.6% of the exchange ceiling. If direct HTTPS to `api.bitget.com` fails (egress IP blocked), the client marks direct unavailable for 10 minutes and runs the whole batch as **one** SSH relay command to the VPS.

### 2.4 Persistent Candlestick Stream

`scripts/run_paper_trader.py --mode daemon` opens `proteus.market.bitget_ws.BitgetCandleStream` at startup, so steady-state screening costs **zero REST requests**.

| Property | Value |
| :--- | :--- |
| Endpoint | `wss://ws.bitget.com/v2/ws/public` (public, no login) |
| Connections | 2 sharded, 46 channels each (Bitget recommends <50/connection) |
| Channels | 92: `candle4H` + `candle15m` per 45 symbols, `candle1Dutc` for BTC/ETH |
| Bootstrap | one REST batch at service start, then deltas only |
| Scan trigger | **15m bar close event** (2 s burst debounce, ≤1 cycle/10 s, ≈2–4 s latency) or 300 s heartbeat |
| Heartbeat | text `ping` every 25 s; reconnect 1→30 s jittered backoff |
| Fallback | missing/stale series (15m > 45 min, 4H > 12 h, 1D > 3 d) → REST per series |
| Without the extra | daemon logs `{"stream": "rest"}` and polls REST exactly as before |

The only new dependency is `websockets>=13,<16`. Bitget limits: 100 connections/IP, 1000 channels/connection, 240 subscription requests/hour/connection, 10 messages/s — all comfortably inside the two-connection design.

---

## 3. CLI & Service Management Commands

### 3.1 Local / Development CLI Commands
```bash
# 1. Run full 36-test verification suite
C:/Workspace/bots/fatty-live-fix/.venv/Scripts/pytest.exe -v

# 2. Run complete Phases 1–6 Cognitive Turing & Constitutional Scorecard
C:/Workspace/bots/fatty-live-fix/.venv/Scripts/python.exe scripts/run_turing_benchmark.py

# 3. Simulate $1,000 paper account across all 97 historical setups
C:/Workspace/bots/fatty-live-fix/.venv/Scripts/python.exe scripts/run_paper_trader.py --mode historical

# 4. Run a single live Bitget scan & step paper ledger
C:/Workspace/bots/fatty-live-fix/.venv/Scripts/python.exe scripts/run_paper_trader.py --mode live-step --refresh-live

# 5. Run Self-Monitoring Watchdog & 4-stage AI-Agent Self-Improver
C:/Workspace/bots/fatty-live-fix/.venv/Scripts/python.exe scripts/run_self_improver.py --learning-rate 0.12
```

### 3.2 Production VPS Service Management (`46.202.155.192`)
```bash
# Check service health and recent daemon ticks
ssh valarion@46.202.155.192 "systemctl status proteus-web.service proteus-paper-daemon.service --no-pager"

# Pull latest main branch and restart both services
ssh valarion@46.202.155.192 "cd /home/valarion/apps/learnernoearner-distillation-engine && git fetch origin && git reset --hard origin/main && sudo -n systemctl restart proteus-web.service proteus-paper-daemon.service"
```

---

## 4. Operator Action Schedule & Graduation Gates

| Gate | Timing / Trigger | Verification Condition | Operator Action |
| :--- | :--- | :--- | :--- |
| **Gate 1: NY Open Check** | Daily `13:00–17:00 UTC` (`20:00–00:00 WIB`) | Inspect Tab 1 open positions for $+1.0R$ `BREAKEVEN_PROTECTED` transitions and 3-slot rotations. | Observation only (no manual edits required). |
| **Gate 2: Bedtime Derisk Check** | Daily `21:00–23:59 UTC` (`04:00–06:59 WIB`) | Confirm profitable open positions transition to `BEDTIME_DERISKED` or `CLOSED_EARLY`. | Observation only. |
| **Gate 3: Canary Live Promotion** | `2026-11-16` (7d) or `closed_positions_count >= 15` | Forward `Win + Scratch >= 75%`, `Max DD <= 3.5R` (`7.0%`), `Watchdog == HEALTHY`, `SHA-256 Chain == VERIFIED`. | Wire Proteus shadow signals into live Bitget canary admission (`$1–$2` risk/trade). |
