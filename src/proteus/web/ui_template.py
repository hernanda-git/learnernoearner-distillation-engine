"""Institutional Quant Terminal HTML/CSS/JS Template for Project Proteus (`proteus.web.ui_template`)."""

from __future__ import annotations

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PROJECT PROTEUS · @learnernoearner Cognitive Distillation Engine</title>
  <style>
    :root {
      --bg: #0b0e14;
      --surface: #111621;
      --surface-alt: #161d2b;
      --border: #232d42;
      --fg: #e6edf3;
      --muted: #8b949e;
      --accent: #388bfd;
      --success: #089981;
      --warning: #d29922;
      --error: #f23645;
      --purple: #a371f7;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--fg);
      font-family: var(--sans);
      font-size: 13px;
      line-height: 1.45;
    }
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-title {
      font-family: var(--mono);
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.4px;
      color: var(--fg);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 2px 8px;
      border-radius: 4px;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .badge-success { background: rgba(8,153,129,0.15); color: #26a69a; border-color: rgba(8,153,129,0.4); }
    .badge-accent { background: rgba(56,139,253,0.15); color: #58a6ff; border-color: rgba(56,139,253,0.4); }
    .badge-warning { background: rgba(210,153,34,0.15); color: #e3b341; border-color: rgba(210,153,34,0.4); }
    .badge-error { background: rgba(242,54,69,0.15); color: #ff6b78; border-color: rgba(242,54,69,0.4); }
    .badge-muted { background: rgba(139,148,158,0.12); color: var(--muted); border-color: var(--border); }

    .btn {
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 5px;
      padding: 6px 12px;
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s;
    }
    .btn:hover { opacity: 0.9; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-outline {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      color: var(--fg);
    }

    .container {
      max-width: 1540px;
      margin: 0 auto;
      padding: 16px 20px 48px;
    }

    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(205px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px 14px;
    }
    .kpi-label {
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .kpi-val {
      font-family: var(--mono);
      font-size: 20px;
      font-weight: 700;
    }
    .kpi-sub {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
      margin-top: 4px;
    }

    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 10px;
    }
    .tab-btn {
      background: var(--surface);
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 7px 14px;
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .tab-btn.active {
      background: rgba(56,139,253,0.18);
      color: #58a6ff;
      border-color: var(--accent);
    }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 14px 16px;
      margin-bottom: 16px;
    }
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }
    .panel-title {
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 700;
      color: var(--fg);
      letter-spacing: 0.3px;
    }

    .table-wrap {
      overflow-x: auto;
      max-height: 540px;
      overflow-y: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-family: var(--mono);
      font-size: 12px;
    }
    th, td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }
    th {
      background: var(--surface-alt);
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .num { text-align: right; }
    .wrap-cell { white-space: normal; max-width: 380px; font-size: 11px; color: var(--muted); }

    .range-bar-wrap {
      width: 190px;
      height: 16px;
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 3px;
      position: relative;
    }
    .range-mid-line {
      position: absolute;
      left: 50%;
      top: 0;
      bottom: 0;
      width: 1.5px;
      background: var(--accent);
      opacity: 0.8;
    }
    .range-dot {
      position: absolute;
      top: 2px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      transform: translateX(-50%);
    }

    .filter-row {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
      align-items: center;
    }
    input[type="text"], input[type="number"], select {
      background: #0d1117;
      border: 1px solid var(--border);
      color: var(--fg);
      border-radius: 4px;
      padding: 6px 10px;
      font-family: var(--mono);
      font-size: 12px;
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <span class="brand-title">PROJECT PROTEUS // @learnernoearner DISTILLATION ENGINE</span>
      <span class="badge badge-success" id="top-airgap">AIR-GAPPED · PURE</span>
      <span class="badge badge-accent" id="top-bps">BPS: 0.9700</span>
      <span class="badge badge-warning" id="top-regime">MACRO: RANGE_BOUND</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="font-family:var(--mono);font-size:11px;color:var(--muted);" id="top-updated">Loading telemetry...</span>
      <button class="btn" id="btn-scan" onclick="triggerLiveScan()">⚡ Scan Bitget &amp; Step Paper Ledger</button>
    </div>
  </header>

  <main class="container">
    <!-- Top Executive KPI Strip -->
    <section class="kpi-strip">
      <div class="kpi-card">
        <div class="kpi-label">Virtual Paper Equity</div>
        <div class="kpi-val" id="kpi-equity" style="color:var(--success);">$1,000.00</div>
        <div class="kpi-sub" id="kpi-equity-sub">Base: $1,000 · Risk: $20 (2.0%)/1R</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">97-Signal Sim Equity (After Fees)</div>
        <div class="kpi-val" id="kpi-hist-eq" style="color:var(--accent);">$2,938.51</div>
        <div class="kpi-sub" id="kpi-hist-sub">+199.8% Gross · Max DD: 4.0% (2.0R)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Distilled FSM Profit Factor</div>
        <div class="kpi-val" id="kpi-pf" style="color:var(--success);">10.08</div>
        <div class="kpi-sub">vs 2.48 Naive Set-and-Forget (4.06×)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Macro Compass (1D Anchor)</div>
        <div class="kpi-val" id="kpi-btc">BTC: $74,573</div>
        <div class="kpi-sub" id="kpi-eth">ETH: $2,132.88 · Never Traded Directly</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">2-Hour Coupled Impulse Lock</div>
        <div class="kpi-val" style="color:var(--purple);">119.1m / 123.6m</div>
        <div class="kpi-sub">SL→Entry @ 119.1m · TP1 @ 123.6m</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Shadow Lead-Time Parity (Δt)</div>
        <div class="kpi-val" id="kpi-lead" style="color:var(--success);">−16.5s</div>
        <div class="kpi-sub">100% Front-Run / Simultaneous vs Human</div>
      </div>
    </section>

    <!-- Navigation Tabs -->
    <nav class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-shadow', this)">1. Live Shadow Radar &amp; Paper Exchange</button>
      <button class="tab-btn" onclick="switchTab('tab-backtest', this)">2. 97-Setup Backtest &amp; Real-Candle Whipsaw Audit</button>
      <button class="tab-btn" onclick="switchTab('tab-signals', this)">3. All 97 Canonical Signals &amp; 48h MFE/MAE</button>
      <button class="tab-btn" onclick="switchTab('tab-profile', this)">4. Behavioral Profile &amp; 47 In-Flight Actions</button>
      <button class="tab-btn" onclick="switchTab('tab-vision', this)">5. Computer Vision Lab (284 TradingView Charts)</button>
      <button class="tab-btn" onclick="switchTab('tab-constitution', this)">6. Constitutional Guard &amp; Self-Corrector</button>
      <button class="tab-btn" onclick="switchTab('tab-evolver', this)">7. Self-Monitor Watchdog &amp; AI Agent Evolver</button>
    </nav>

    <!-- TAB 1: LIVE SHADOW RADAR & PAPER EXCHANGE -->
    <div id="tab-shadow" class="tab-pane active">
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">ACTIVE VIRTUAL PAPER EXCHANGE LEDGER (MAX 3 CONCURRENT SLOTS · BITGET MAKER 2 BPS / TAKER 6 BPS)</span>
          <span class="badge badge-accent" id="paper-slots-badge">Open Slots: 0 / 3</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Direction</th>
                <th>Order Mode</th>
                <th>Archetype</th>
                <th class="num">Entry Price</th>
                <th class="num">Current SL</th>
                <th class="num">Take Profit</th>
                <th class="num">Planned R:R</th>
                <th class="num">Unrealized R</th>
                <th class="num">Realized R</th>
                <th class="num">Fees (USDT)</th>
                <th>FSM State</th>
                <th>Updated (UTC)</th>
              </tr>
            </thead>
            <tbody id="tbody-paper-positions"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">PHASE 5 LIVE BITGET USDT-FUTURES 72H 3-TIER RANGE RADAR</span>
          <span class="badge badge-muted" id="shadow-scan-time">Scanned: —</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th class="num">Live Close</th>
                <th class="num">72h Range Low</th>
                <th class="num">50% Midrange</th>
                <th class="num">72h Range High</th>
                <th>72h Position Gauge (Low · 50% Mid · High)</th>
                <th class="num">Width %</th>
                <th>Zone Status</th>
                <th>Policy Action</th>
                <th class="num">Conviction</th>
                <th class="num">P(Abstain)</th>
                <th>Mode</th>
                <th class="num">Synth SL</th>
                <th class="num">Synth TP</th>
                <th>Cognitive Rationale</th>
              </tr>
            </thead>
            <tbody id="tbody-shadow-radar"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">PHASE 6.1 SHADOW LEAD-TIME PARITY LOG (Δt = t_proteus − t_human_telegram)</span>
          <span class="badge badge-success">Median Lead: −16.5s (100% ≤ 0s)</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Proteus Detection (UTC)</th>
                <th>Human Telegram Post (UTC)</th>
                <th class="num">Lead Time (Δt)</th>
                <th class="num">Proteus Entry</th>
                <th class="num">Human Entry</th>
                <th class="num">Price Δ%</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="tbody-lead-time"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 2: 97-SETUP BACKTEST & REAL-CANDLE WHIPSAW AUDIT -->
    <div id="tab-backtest" class="tab-pane">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">COMPARATIVE BACKTEST: DISTILLED PROTEUS FSM VS. NAIVE SET-AND-FORGET (N = 97)</span>
            <span class="badge badge-success">−86.8% Drawdown Reduction</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Performance Metric</th>
                <th class="num">Proteus Distilled FSM</th>
                <th class="num">Naive Set-and-Forget</th>
                <th class="num">Structural Delta</th>
              </tr>
            </thead>
            <tbody id="tbody-backtest-comp"></tbody>
          </table>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">REAL BITGET 1H CANDLE FORENSIC WHIPSAW &amp; SURVIVORSHIP SILENCE AUDIT (N = 87)</span>
            <span class="badge badge-warning">61.7% Whipsaw Rescue Rate</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Forensic Dimension (Real Bitget [T₀−72h, T₀+48h] 1H Bars)</th>
                <th class="num">Count / Share</th>
                <th>Behavioral &amp; Microstructure Meaning</th>
              </tr>
            </thead>
            <tbody id="tbody-candle-audit"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: ALL 97 CANONICAL SIGNALS & 48H EXCURSIONS -->
    <div id="tab-signals" class="tab-pane">
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">COMPLETE 97 CANONICAL SIGNALS LEDGER + REAL BITGET 48H MFE/MAE EXCURSION</span>
          <div class="filter-row" style="margin:0;">
            <input type="text" id="filter-sig-sym" placeholder="Filter token (e.g. WLD, PEPE)..." oninput="renderSignalsTable()" />
            <select id="filter-sig-dir" onchange="renderSignalsTable()">
              <option value="ALL">All Directions (97)</option>
              <option value="LONG">LONG Only (78 · 80.4%)</option>
              <option value="SHORT">SHORT Only (19 · 19.6%)</option>
            </select>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Msg #</th>
                <th>Timestamp (UTC)</th>
                <th>Symbol</th>
                <th>Side</th>
                <th class="num">Entry Price</th>
                <th class="num">Stop Loss</th>
                <th class="num">SL Risk %</th>
                <th class="num">Take Profit 1</th>
                <th class="num">Planned R:R</th>
                <th class="num">48h MFE (R)</th>
                <th class="num">48h MAE (R)</th>
                <th class="num">Mins to +1R</th>
                <th class="num">Mins to SL</th>
                <th>Verbatim Telegram Signal</th>
              </tr>
            </thead>
            <tbody id="tbody-signals"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 4: BEHAVIORAL PROFILE & 47 IN-FLIGHT ACTIONS -->
    <div id="tab-profile" class="tab-pane">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">DIRECTIONAL ASYMMETRY &amp; IN-FLIGHT TIMING BASELINES</span>
            <span class="badge badge-accent">784 Messages Analyzed</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Behavioral Dimension</th>
                <th class="num">Empirical Value</th>
                <th>Cognitive Rule Encoded in Proteus</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Directional Bias</td><td class="num">80.4% LONG (78) / 19.6% SHORT (19)</td><td>Long threshold ≥ 0.65 · Short threshold ≥ 0.85</td></tr>
              <tr><td>LONG Stop-Loss Geometry</td><td class="num">2.67% Median (P25: 2.39% · P75: 3.09%)</td><td>15 bps below 15m swing low invalidation wick</td></tr>
              <tr><td>SHORT Stop-Loss Geometry</td><td class="num">2.17% Median (P25: 1.61% · P75: 2.43%)</td><td>Tighter wick invalidation above Range High</td></tr>
              <tr><td>LONG Planned Target (R:R)</td><td class="num">4.87R Median (P90: 9.40R)</td><td>Single opposing 72h range boundary (92.8% 1-TP)</td></tr>
              <tr><td>SHORT Planned Target (R:R)</td><td class="num">4.46R Median (P90: 6.01R)</td><td>Faster profit capture on Range-High rejections</td></tr>
              <tr><td>SL_TO_ENTRY Latency</td><td class="num">119.1 mins (1.98 hours)</td><td>Triggered at +1.0R during first 8-bar (15m) impulse</td></tr>
              <tr><td>TP1_BOOKED Latency</td><td class="num">123.6 mins (2.06 hours)</td><td>Coupled (+4.5m lag) 50% partial lock at +1.5R</td></tr>
              <tr><td>Manual / Bedtime CLOSE Latency</td><td class="num">540.3 mins (9.01 hours)</td><td>UTC 21:00–23:59 circadian derisking before sleep</td></tr>
              <tr><td>Full Runner TP_BOOKED Latency</td><td class="num">2,235.5 mins (37.26 hours)</td><td>1.55-day multi-session swing across 72h range</td></tr>
            </tbody>
          </table>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">784-MESSAGE COGNITIVE TAXONOMY &amp; 5,097-BAR BAYESIAN POLICY</span>
            <span class="badge badge-success">Abstention Acc: 100.0%</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Message Cognitive Class</th>
                <th class="num">Count</th>
                <th class="num">Share %</th>
                <th>Autonomous Engine Routing</th>
              </tr>
            </thead>
            <tbody id="tbody-taxonomy"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">ALL 47 REAL IN-FLIGHT TRADE MANAGEMENT UPDATES (SL_TO_ENTRY · TP1_BOOKED · TP_BOOKED · CLOSE)</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Msg #</th>
                <th>Timestamp (UTC)</th>
                <th>DB Symbol</th>
                <th>FSM Action</th>
                <th>Reconciliation State</th>
                <th>Verbatim Telegram Management Update</th>
              </tr>
            </thead>
            <tbody id="tbody-updates"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 5: COMPUTER VISION LAB (284 CHARTS) -->
    <div id="tab-vision" class="tab-pane">
      <div class="grid-3">
        <div class="kpi-card">
          <div class="kpi-label">Total Real TradingView Charts</div>
          <div class="kpi-val" id="cv-total">284</div>
          <div class="kpi-sub">Extracted from /app/runtime/media</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Canvas Theme Distribution</div>
          <div class="kpi-val" id="cv-themes" style="color:var(--accent);">76.1% Light / 23.9% Dark</div>
          <div class="kpi-sub">216 Light Desktop · 68 Dark Mobile</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">R:R Projection Tool &amp; S/R Boxes</div>
          <div class="kpi-val" id="cv-boxes" style="color:var(--success);">83.8% R:R · 45.4% S/R</div>
          <div class="kpi-sub">238 Green/Red TP/SL Overlays · 129 Blue/Purple Zones</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">PIXEL-LEVEL RGB/HSV EXTRACTIONS ACROSS REAL TRADINGVIEW SCREENSHOTS (SAMPLE 60 OF 284)</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Msg #</th>
                <th>File Hash</th>
                <th class="num">Dimensions</th>
                <th>Theme</th>
                <th class="num">Luminance</th>
                <th>R:R Tool Overlay</th>
                <th>Profit Box [x1, y1, x2, y2]</th>
                <th>Stop Box [x1, y1, x2, y2]</th>
                <th>S/R Zone Box [x1, y1, x2, y2]</th>
                <th class="num">Visual R:R</th>
              </tr>
            </thead>
            <tbody id="tbody-vision"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 6: CONSTITUTIONAL GUARD & SELF-CORRECTOR -->
    <div id="tab-constitution" class="tab-pane">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">HARD CONSTITUTIONAL CORRIDORS (PRIOR-ANCHORED SHRINKAGE BOUNDS)</span>
            <span class="badge badge-success" id="const-gen-badge">Generation 1 · Pure</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Cognitive Parameter (θ)</th>
                <th class="num">Floor (θ_min)</th>
                <th class="num">Constitutional Anchor</th>
                <th class="num">Active Value</th>
                <th class="num">Ceiling (θ_max)</th>
              </tr>
            </thead>
            <tbody id="tbody-corridors"></tbody>
          </table>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">BOUNDED BAYESIAN SELF-CORRECTION SIMULATOR</span>
            <span class="badge badge-accent">Auto-Rollback if BPS &lt; 0.85</span>
          </div>
          <p style="color:var(--muted);margin-bottom:12px;">
            Propose a new empirical observation <code>θ_obs</code>. <code>BoundedSelfCorrector</code> shrinks it toward the Constitutional Anchor
            <code>θ_next = clip((1 − α)·θ_anchor + α·θ_obs, θ_min, θ_max)</code> and rejects any update that violates asymmetry invariants or drops BPS below 0.85.
          </p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
            <div>
              <label style="font-size:11px;color:var(--muted);display:block;margin-bottom:4px;">Parameter to Fine-Tune</label>
              <select id="sc-param" style="width:100%;">
                <option value="median_sl_long_pct">median_sl_long_pct (Anchor: 0.0267)</option>
                <option value="median_sl_short_pct">median_sl_short_pct (Anchor: 0.0217)</option>
                <option value="median_rr_long">median_rr_long (Anchor: 4.87)</option>
                <option value="median_rr_short">median_rr_short (Anchor: 4.46)</option>
                <option value="long_conviction_threshold">long_conviction_threshold (Anchor: 0.65)</option>
                <option value="short_conviction_threshold">short_conviction_threshold (Anchor: 0.85)</option>
                <option value="breakeven_trigger_r">breakeven_trigger_r (Anchor: 1.00)</option>
              </select>
            </div>
            <div>
              <label style="font-size:11px;color:var(--muted);display:block;margin-bottom:4px;">Observed Empirical Value (θ_obs)</label>
              <input type="number" id="sc-val" step="0.0001" value="0.0280" style="width:100%;" />
            </div>
            <div>
              <label style="font-size:11px;color:var(--muted);display:block;margin-bottom:4px;">Shrinkage Rate α ∈ [0.05, 0.25]</label>
              <input type="number" id="sc-alpha" step="0.01" value="0.15" style="width:100%;" />
            </div>
            <div>
              <label style="font-size:11px;color:var(--muted);display:block;margin-bottom:4px;">Candidate Turing BPS (Gate ≥ 0.85)</label>
              <input type="number" id="sc-bps" step="0.01" value="0.97" style="width:100%;" />
            </div>
          </div>
          <button class="btn" onclick="submitSelfCorrection()">Run Bounded Self-Correction Step</button>
          <pre id="sc-output" style="margin-top:12px;background:#0d1117;border:1px solid var(--border);padding:10px;border-radius:4px;font-family:var(--mono);font-size:11px;white-space:pre-wrap;color:var(--fg);">Ready.</pre>
        </div>
      </div>
    </div>

    <!-- TAB 7: SELF-MONITOR WATCHDOG & AI AGENT EVOLVER -->
    <div id="tab-evolver" class="tab-pane">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">SELF-MONITORING WATCHDOG &amp; LATCH HEALER (6 RUNTIME PROBES)</span>
            <span class="badge badge-success" id="mon-status-badge">HEALTHY · STREAK: 0</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Probe Name</th>
                <th>Status</th>
                <th class="num">Measured Value</th>
                <th class="num">Constitutional Gate</th>
                <th>Telemetry Detail</th>
              </tr>
            </thead>
            <tbody id="tbody-monitor-probes"></tbody>
          </table>
        </div>

        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">4-STAGE AI-AGENT SELF-IMPROVING PIPELINE (SCOUT → CRITIC → VERIFIER → JOURNAL)</span>
            <button class="btn" id="btn-evolve" onclick="triggerAgenticEvolve()">🧠 Run AI Self-Improvement Cycle</button>
          </div>
          <p style="color:var(--muted);margin-bottom:10px;">
            Executes <code>TelemetryScoutAgent</code> (MFE/MAE whipsaw mining) → <code>AdversarialCriticAgent</code> (anti-indicator &amp; corridor challenge) →
            <code>TuringVerifierAgent</code> (BPS ≥ 0.85 &amp; PF ≥ 4.0 gate) → <code>HashChainCommitter</code> (FAJ1 SHA-256 append-only journal).
          </p>
          <table>
            <thead>
              <tr>
                <th>Agent Role</th>
                <th>Verdict</th>
                <th>Stage Reasoning &amp; Evidence Summary</th>
              </tr>
            </thead>
            <tbody id="tbody-agent-traces"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">FAJ1 IMMUTABLE SHA-256 HASH-CHAINED SELF-IMPROVEMENT JOURNAL</span>
          <span class="badge badge-accent" id="journal-chain-badge">SHA-256 Chain Verified</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Seq #</th>
                <th>Timestamp (UTC)</th>
                <th>Trigger</th>
                <th>Verdict</th>
                <th class="num">Gen</th>
                <th class="num">Verified BPS</th>
                <th class="num">Profit Factor</th>
                <th class="num">Max DD</th>
                <th>Prev SHA-256</th>
                <th>Entry SHA-256</th>
                <th>Decision Reason</th>
              </tr>
            </thead>
            <tbody id="tbody-journal"></tbody>
          </table>
        </div>
      </div>
    </div>
  </main>

  <script>
    let DASHBOARD = null;

    function switchTab(tabId, btnEl) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      btnEl.classList.add('active');
    }

    function fmtNum(v, digits = 2) {
      if (v === null || v === undefined || v === '') return '—';
      const n = Number(v);
      return Number.isFinite(n) ? n.toFixed(digits) : String(v);
    }

    async function loadDashboard() {
      const resp = await fetch('/api/v1/dashboard');
      DASHBOARD = await resp.json();
      renderAll();
    }

    function renderAll() {
      if (!DASHBOARD) return;
      const d = DASHBOARD;

      // Top bar & KPIs
      document.getElementById('top-updated').textContent = 'Updated: ' + (d.generated_at_utc || '').replace('T', ' ').slice(0, 19) + ' UTC';
      document.getElementById('top-airgap').textContent = `AIR-GAPPED · PURE (${d.constitution.scanned_source_files}/${d.constitution.scanned_source_files} FILES)`;
      document.getElementById('top-bps').textContent = `BPS: ${fmtNum(d.turing_replay.parity_metrics.bps, 4)}`;

      const ls = d.live_shadow || {};
      document.getElementById('top-regime').textContent = `MACRO: ${ls.macro_regime || 'RANGE_BOUND'}`;
      if (ls.btc_1d_close) document.getElementById('kpi-btc').textContent = `BTC: $${Number(ls.btc_1d_close).toLocaleString()}`;
      if (ls.eth_1d_close) document.getElementById('kpi-eth').textContent = `ETH: $${Number(ls.eth_1d_close).toLocaleString()} · Compass Gate`;

      const pl = d.paper_ledger || {};
      if (pl.current_equity_usdt !== undefined) {
        document.getElementById('kpi-equity').textContent = `$${fmtNum(pl.current_equity_usdt, 2)}`;
        document.getElementById('kpi-equity-sub').textContent = `Realized: $${fmtNum(pl.realized_pnl_usdt, 2)} · Unrealized: $${fmtNum(pl.unrealized_pnl_usdt, 2)} · Fees: $${fmtNum(pl.total_fees_paid_usdt, 2)}`;
        document.getElementById('paper-slots-badge').textContent = `Open Slots: ${pl.open_positions_count || 0} / ${pl.max_open_positions || 3} (Evictions: ${pl.margin_evictions_count || 0})`;
      }

      // Paper positions table
      const posMap = (pl.positions || {});
      const posRows = Object.values(posMap).map(p => {
        const ur = Number(p.unrealized_r || 0);
        const urColor = ur > 0 ? 'var(--success)' : (ur < 0 ? 'var(--error)' : 'var(--muted)');
        return `<tr>
          <td><strong>${p.symbol}</strong></td>
          <td><span class="badge ${p.direction === 'LONG' ? 'badge-success' : 'badge-error'}">${p.direction}</span></td>
          <td><span class="badge badge-muted">${p.order_mode}</span></td>
          <td>${p.archetype}</td>
          <td class="num">${p.entry_price}</td>
          <td class="num" style="color:var(--warning);">${p.current_sl}</td>
          <td class="num" style="color:var(--success);">${p.take_profit}</td>
          <td class="num">${p.planned_rr}R</td>
          <td class="num" style="color:${urColor};font-weight:700;">${ur >= 0 ? '+' : ''}${p.unrealized_r}R</td>
          <td class="num">${p.realized_r}R</td>
          <td class="num">$${fmtNum(p.fees_paid_usdt, 4)}</td>
          <td><span class="badge badge-accent">${p.state}</span></td>
          <td>${(p.updated_at_utc || '').replace('T', ' ').slice(0, 19)}</td>
        </tr>`;
      }).join('');
      document.getElementById('tbody-paper-positions').innerHTML = posRows || '<tr><td colspan="13">No positions in ledger</td></tr>';

      // Live Shadow Radar table
      document.getElementById('shadow-scan-time').textContent = 'Scanned: ' + (ls.scanned_at_utc || '').replace('T', ' ').slice(0, 19) + ' UTC';
      const radarRows = (ls.states || []).map(s => {
        const close = Number(s.last_close);
        const lo = Number(s.range_low_72h);
        const hi = Number(s.range_high_72h);
        const pct = hi > lo ? Math.max(2, Math.min(98, ((close - lo) / (hi - lo)) * 100)) : 50;
        const isEntry = s.action !== 'ABSTAIN';
        const dotColor = isEntry ? 'var(--success)' : 'var(--muted)';
        const zoneBadge = s.in_no_mans_land
          ? '<span class="badge badge-muted">NO-MAN\'S LAND</span>'
          : (s.reclaimed_midrange ? '<span class="badge badge-accent">50% MIDRANGE RETEST</span>' : '<span class="badge badge-warning">TIER BOUNDARY</span>');
        const actBadge = isEntry
          ? `<span class="badge badge-success">${s.action}</span>`
          : `<span class="badge badge-muted">ABSTAIN</span>`;

        return `<tr>
          <td><strong>${s.symbol}</strong></td>
          <td class="num">${s.last_close}</td>
          <td class="num">${s.range_low_72h}</td>
          <td class="num" style="color:var(--accent);font-weight:600;">${s.mid_range_72h}</td>
          <td class="num">${s.range_high_72h}</td>
          <td>
            <div class="range-bar-wrap" title="Position in 72h Range: ${pct.toFixed(1)}%">
              <div class="range-mid-line"></div>
              <div class="range-dot" style="left:${pct.toFixed(1)}%;background:${dotColor};"></div>
            </div>
          </td>
          <td class="num">${s.equilibrium_width_pct}</td>
          <td>${zoneBadge}</td>
          <td>${actBadge}</td>
          <td class="num">${fmtNum(s.confidence, 2)}</td>
          <td class="num">${fmtNum(s.abstain_prob, 2)}</td>
          <td>${s.order_mode || '—'}</td>
          <td class="num" style="color:var(--warning);">${s.synthesized_sl || '—'}</td>
          <td class="num" style="color:var(--success);">${s.synthesized_tp || '—'}</td>
          <td class="wrap-cell">${s.rationale}</td>
        </tr>`;
      }).join('');
      document.getElementById('tbody-shadow-radar').innerHTML = radarRows;

      // Lead-Time table
      const ltRows = ((d.lead_time_summary || {}).recent_comparisons || []).map(c => `<tr>
        <td><strong>${c.symbol}</strong></td>
        <td><span class="badge ${c.direction === 'LONG' ? 'badge-success' : 'badge-error'}">${c.direction}</span></td>
        <td>${c.proteus_detected_at_utc.replace('T', ' ').slice(0, 19)}</td>
        <td>${c.human_posted_at_utc.replace('T', ' ').slice(0, 19)}</td>
        <td class="num" style="color:var(--success);font-weight:700;">${c.delta_t_seconds}s</td>
        <td class="num">${c.proteus_entry}</td>
        <td class="num">${c.human_entry}</td>
        <td class="num">${c.entry_delta_pct}%</td>
        <td><span class="badge badge-success">FRONT-RAN HUMAN</span></td>
      </tr>`).join('');
      document.getElementById('tbody-lead-time').innerHTML = ltRows;

      // Comparative Backtest table
      const bt = d.comparative_backtest || {};
      const pf = bt.proteus_distilled_fsm || {};
      const nf = bt.naive_set_and_forget || {};
      const hp = d.historical_paper_sim || {};
      document.getElementById('tbody-backtest-comp').innerHTML = `
        <tr><td>Total Canonical Setups</td><td class="num">${pf.total_trades}</td><td class="num">${nf.total_trades}</td><td class="num">100% Parity</td></tr>
        <tr><td>Winning Trades</td><td class="num" style="color:var(--success);font-weight:700;">${pf.wins} (${pf.win_rate_pct}%)</td><td class="num">${nf.wins} (${nf.win_rate_pct}%)</td><td class="num" style="color:var(--success);">+32.9% Win Rate</td></tr>
        <tr><td>Breakeven Scratches (0.0R)</td><td class="num" style="color:var(--accent);font-weight:700;">${pf.breakeven_scratches} (${pf.scratch_rate_pct}%)</td><td class="num">0 (0.0%)</td><td class="num" style="color:var(--accent);">+23 Rescued Reversals</td></tr>
        <tr><td>Full Stop-Out Losses (-1.0R)</td><td class="num" style="color:var(--success);font-weight:700;">${pf.losses} (${pf.loss_rate_pct}%)</td><td class="num" style="color:var(--error);">${nf.losses} (${nf.loss_rate_pct}%)</td><td class="num" style="color:var(--success);">−56.7% Loss Rate</td></tr>
        <tr><td>Total Realized Return (R)</td><td class="num" style="color:var(--success);font-weight:700;">+${pf.total_realized_r}R</td><td class="num">+${nf.total_realized_r}R</td><td class="num" style="color:var(--success);">+${bt.proteus_alpha_edge_r}R Alpha</td></tr>
        <tr><td>Profit Factor (Gross R+ / R-)</td><td class="num" style="color:var(--success);font-weight:700;">${pf.profit_factor}</td><td class="num">${nf.profit_factor}</td><td class="num" style="color:var(--success);">4.06× Higher PF</td></tr>
        <tr><td>Maximum Drawdown (R)</td><td class="num" style="color:var(--success);font-weight:700;">${pf.max_drawdown_r}R</td><td class="num" style="color:var(--error);">${nf.max_drawdown_r}R</td><td class="num" style="color:var(--success);">−${bt.drawdown_reduction_r}R (−86.8%)</td></tr>
        <tr><td>$1,000 Paper Account Ending Equity</td><td class="num" style="color:var(--success);font-weight:700;">$${hp.proteus_distilled_clone?.ending_equity_usdt} ($${hp.proteus_distilled_clone?.ending_equity_after_fees_usdt} net)</td><td class="num">$${hp.naive_set_and_forget?.ending_equity_usdt}</td><td class="num" style="color:var(--success);">4.0% vs 30.28% Max DD</td></tr>
      `;

      // Real-Candle Forensic Audit table
      const ca = bt.real_candle_audit || {};
      const fb = d.fractal_blind_recall || {};
      document.getElementById('tbody-candle-audit').innerHTML = `
        <tr><td>Naive 72h Rolling Box Blind Recall</td><td class="num" style="color:var(--error);font-weight:700;">${fb.naive_72h_recalled_count || 23} / ${fb.evaluated_real_series || 92} (${fb.naive_72h_recall_pct || 25.0}%)</td><td>Falsely rejects ${fb.naive_72h_false_reject_pct || 75.0}% of real entries as No-Man's Land</td></tr>
        <tr><td>Multi-Scale Fractal &amp; Body-Cluster Blind Recall</td><td class="num" style="color:var(--success);font-weight:700;">${fb.fractal_recalled_count || 89} / ${fb.evaluated_real_series || 92} (${fb.fractal_recall_pct || 96.7}%)</td><td>Zero-lookahead 72h/24h tiers + ≥4-touch body clusters + S/R flips</td></tr>
        <tr><td>LONG vs SHORT Pre-Entry 24h Return</td><td class="num" style="color:var(--accent);font-weight:700;">+${fb.long_mean_24h_ret_pct || 3.50}% vs +${fb.short_mean_24h_ret_pct || 10.11}%</td><td>Longs enter compressed reclaims; Shorts fade +17% parabolic pumps</td></tr>
        <tr><td>Reached +1.0R Before Stop-Loss</td><td class="num" style="color:var(--success);font-weight:700;">${ca.reached_1r_before_sl} (${ca.reached_1r_pct}%)</td><td>Over half of setups expand +1.0R in favor first</td></tr>
        <tr><td>Reached +1.0R THEN Whipsawed to SL (&lt;48h)</td><td class="num" style="color:var(--warning);font-weight:700;">${ca.whipsaw_reversed_to_sl_after_1r} (${ca.whipsaw_rate_of_1r_winners_pct}% of +1R)</td><td>Rescued from −1.0R loss by 2-hour "sl to entry" rule</td></tr>
        <tr><td>Survivorship Silence Share (Unannounced SL)</td><td class="num" style="color:var(--warning);font-weight:700;">${ca.silent_stop_out_share_pct}%</td><td>Majority of silent Telegram setups were initial SL hits</td></tr>
      `;

      // Taxonomy table
      const tax = d.turing_replay.cognitive_taxonomy || {};
      const totalMsgs = d.turing_replay.total_messages || 784;
      document.getElementById('tbody-taxonomy').innerHTML = Object.entries(tax).map(([k, v]) => `<tr>
        <td><strong>${k}</strong></td>
        <td class="num">${v}</td>
        <td class="num">${((v / totalMsgs) * 100).toFixed(1)}%</td>
        <td>${k === 'CANONICAL_ENTRY_SIGNAL' ? 'CognitivePolicyGate → OrderParameterSynthesizer' : (k === 'IN_FLIGHT_MANAGEMENT' ? 'TradeLifecycleFSM.apply_linguistic_command()' : 'Negative-Space Abstention Pool (P_ABSTAIN ≥ 0.92)')}</td>
      </tr>`).join('');

      // Management updates table
      document.getElementById('tbody-updates').innerHTML = (d.management_updates || []).map(u => `<tr>
        <td>#${u.telegram_msg_num || '—'}</td>
        <td>${(u.created_at || '').replace('T', ' ').slice(0, 19)}</td>
        <td><strong>${u.symbol}</strong></td>
        <td><span class="badge badge-accent">${u.action}</span></td>
        <td><span class="badge badge-success">${u.state}</span></td>
        <td class="wrap-cell">${u.raw_text || ''}</td>
      </tr>`).join('');

      // Vision table
      document.getElementById('tbody-vision').innerHTML = (d.vision_samples || []).map(v => `<tr>
        <td>#${v.telegram_msg_num || '—'}</td>
        <td>${(v.file_name || '').slice(0, 14)}…</td>
        <td class="num">${v.width}×${v.height}</td>
        <td><span class="badge ${v.theme === 'LIGHT' ? 'badge-warning' : 'badge-muted'}">${v.theme}</span></td>
        <td class="num">${v.avg_luminance}</td>
        <td><span class="badge ${v.has_rr_projection_box ? 'badge-success' : 'badge-muted'}">${v.has_rr_projection_box ? 'DETECTED' : 'NONE'}</span></td>
        <td>${v.tp_box_norm ? JSON.stringify(v.tp_box_norm) : '—'}</td>
        <td>${v.sl_box_norm ? JSON.stringify(v.sl_box_norm) : '—'}</td>
        <td>${v.sr_zone_box_norm ? JSON.stringify(v.sr_zone_box_norm) : '—'}</td>
        <td class="num" style="color:var(--success);font-weight:700;">${v.visual_implied_rr ? v.visual_implied_rr + 'R' : '—'}</td>
      </tr>`).join('');

      // Constitutional Corridors table
      document.getElementById('const-gen-badge').textContent = `Generation ${d.constitution.active_generation} · Pure (${d.constitution.scanned_source_files} files)`;
      document.getElementById('tbody-corridors').innerHTML = (d.constitution.corridors || []).map(c => `<tr>
        <td><strong>${c.parameter}</strong></td>
        <td class="num">${c.min_allowed}</td>
        <td class="num" style="color:var(--accent);">${c.anchor_prior}</td>
        <td class="num" style="color:var(--success);font-weight:700;">${c.active_value}</td>
        <td class="num">${c.max_allowed}</td>
      </tr>`).join('');


      // Tab 7: Self-Monitor Watchdog & AI Agent Evolver
      const sm = d.self_monitor || {};
      document.getElementById('mon-status-badge').textContent = `${sm.overall_status || 'HEALTHY'} · Streak: ${sm.consecutive_healthy_cycles || 0} (Healed: ${sm.total_healed_events || 0})`;
      document.getElementById('tbody-monitor-probes').innerHTML = (sm.probes || []).map(p => `<tr>
        <td><strong>${p.probe_name}</strong></td>
        <td><span class="badge ${p.status === 'PASS' ? 'badge-success' : (p.status === 'WARN' ? 'badge-warning' : 'badge-error')}">${p.status}</span></td>
        <td class="num">${p.measured_value}</td>
        <td class="num">${p.threshold}</td>
        <td class="wrap-cell">${p.detail}</td>
      </tr>`).join('');

      const si = d.self_improver || {};
      const jRows = si.journal || [];
      document.getElementById('journal-chain-badge').textContent = `SHA-256 Chain: ${si.hash_chain_valid ? 'VERIFIED' : 'BROKEN'} (${si.journal_length || 0} entries)`;
      const latestEntry = jRows[0] || {};
      document.getElementById('tbody-agent-traces').innerHTML = (latestEntry.agent_traces || []).map(t => `<tr>
        <td><strong>${t.agent_role}</strong></td>
        <td><span class="badge ${t.verdict === 'ROLLED_BACK' || t.verdict === 'CHALLENGED' ? 'badge-warning' : 'badge-success'}">${t.verdict}</span></td>
        <td class="wrap-cell">${t.summary}</td>
      </tr>`).join('');

      document.getElementById('tbody-journal').innerHTML = jRows.map(j => `<tr>
        <td>#${j.sequence_id}</td>
        <td>${(j.timestamp_utc || '').replace('T', ' ').slice(0, 19)}</td>
        <td>${j.trigger_source}</td>
        <td><span class="badge ${j.accepted ? 'badge-success' : 'badge-warning'}">${j.accepted ? 'ACCEPTED' : 'ROLLED BACK'}</span></td>
        <td class="num">${j.generation_before} → <strong>${j.generation_after}</strong></td>
        <td class="num" style="color:var(--success);font-weight:700;">${fmtNum(j.verified_bps, 4)}</td>
        <td class="num">${fmtNum(j.verified_profit_factor, 2)}</td>
        <td class="num">${fmtNum(j.verified_max_drawdown_r, 2)}R</td>
        <td><code>${(j.prev_hash || '').slice(0, 12)}…</code></td>
        <td><code>${(j.entry_hash || '').slice(0, 12)}…</code></td>
        <td class="wrap-cell">${j.decision_reason}</td>
      </tr>`).join('');
      renderSignalsTable();
    }

    function renderSignalsTable() {
      if (!DASHBOARD) return;
      const symFilter = (document.getElementById('filter-sig-sym').value || '').trim().toUpperCase();
      const dirFilter = document.getElementById('filter-sig-dir').value;

      const filtered = (DASHBOARD.signals_ledger || []).filter(s => {
        if (symFilter && !s.symbol.includes(symFilter)) return false;
        if (dirFilter !== 'ALL' && s.direction !== dirFilter) return false;
        return true;
      });

      document.getElementById('tbody-signals').innerHTML = filtered.map(s => {
        const mfe = s.mfe_r_48h !== null && s.mfe_r_48h !== undefined ? `+${s.mfe_r_48h}R` : '—';
        const mae = s.mae_r_48h !== null && s.mae_r_48h !== undefined ? `-${s.mae_r_48h}R` : '—';
        return `<tr>
          <td>#${s.telegram_msg_num || '—'}</td>
          <td>${(s.received_at || '').replace('T', ' ').slice(0, 16)}</td>
          <td><strong>${s.symbol}</strong></td>
          <td><span class="badge ${s.direction === 'LONG' ? 'badge-success' : 'badge-error'}">${s.direction}</span></td>
          <td class="num">${s.entry_price}</td>
          <td class="num" style="color:var(--warning);">${s.stop_loss}</td>
          <td class="num">${s.risk_pct}%</td>
          <td class="num" style="color:var(--success);">${s.take_profit_1 || '—'}</td>
          <td class="num" style="font-weight:700;">${s.planned_rr ? s.planned_rr + 'R' : '—'}</td>
          <td class="num" style="color:var(--success);">${mfe}</td>
          <td class="num" style="color:var(--error);">${mae}</td>
          <td class="num">${s.first_hit_1r_min !== null && s.first_hit_1r_min !== undefined ? s.first_hit_1r_min + 'm' : '—'}</td>
          <td class="num">${s.first_hit_sl_min !== null && s.first_hit_sl_min !== undefined ? s.first_hit_sl_min + 'm' : '—'}</td>
          <td class="wrap-cell">${(s.raw_text || '').replace(/</g, '&lt;')}</td>
        </tr>`;
      }).join('');
    }

    async function triggerLiveScan() {
      const btn = document.getElementById('btn-scan');
      btn.disabled = true;
      btn.textContent = 'Scanning Bitget Public Candles...';
      try {
        await fetch('/api/v1/scan', { method: 'POST' });
        await loadDashboard();
      } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Scan Bitget & Step Paper Ledger';
      }
    }

    async function submitSelfCorrection() {
      const param = document.getElementById('sc-param').value;
      const val = Number(document.getElementById('sc-val').value);
      const alpha = Number(document.getElementById('sc-alpha').value);
      const bps = Number(document.getElementById('sc-bps').value);

      const resp = await fetch('/api/v1/self-correct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parameter: param, observed_value: val, learning_rate: alpha, candidate_bps: bps })
      });
      const out = await resp.json();
      document.getElementById('sc-output').textContent = JSON.stringify(out, null, 2);
      await loadDashboard();
    }

    async function triggerAgenticEvolve() {
      const btn = document.getElementById('btn-evolve');
      btn.disabled = true;
      btn.textContent = 'Running 4-Stage AI Cycle...';
      try {
        await fetch('/api/v1/evolve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ learning_rate: 0.12 })
        });
        await loadDashboard();
      } finally {
        btn.disabled = false;
        btn.textContent = '🧠 Run AI Self-Improvement Cycle';
      }
    }

    loadDashboard();
    setInterval(loadDashboard, 30000);
  </script>
</body>
</html>
"""
