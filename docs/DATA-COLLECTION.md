# Data Collection Runbook

This document is the executable companion to the audit's "data sufficiency" section. It records what can be collected now, what cannot, and the exact commands.

## 1. What the corpus has

| Asset | Location | N |
|---|---|---:|
| Canonical signals | `benchmarks/corpus/canonical_signals.json` | 95 (76 L / 19 S) |
| Telegram messages | `benchmarks/corpus/telegram_messages.json` | 784 |
| Management updates | `benchmarks/corpus/management_updates.json` | 47 |
| Resolved 48h trajectories | `benchmarks/corpus/signal_candle_trajectories.json` | 86 |
| 1H candles per signal | `benchmarks/corpus/real_1h_candles_by_signal.json` | 91 usable pre-series |
| Chart screenshots | `data/media/` (gitignored) | 284 |
| Vision annotations | `benchmarks/corpus/vision_annotations.json` | 284 legacy color-mask rows, **0 human labels** |

## 2. 1-minute candles

The backtest needs `[T0 − 72h, T0 + 48h]` at 1m to resolve intrabar stop/target order.

```bash
# newest 10 signals, output outside git
python scripts/fetch_1m_candles.py --latest 10 --out data/1m

# specific symbols
python scripts/fetch_1m_candles.py --symbols PUMP,WLD,ENA --out data/1m

# resume / refetch
python scripts/fetch_1m_candles.py --latest 10 --out data/1m --force
```

Output: one JSON per signal (`rows`, `candles: [[ts_ms,o,h,l,c,v], ...]`) plus `MANIFEST.json` with per-file SHA-256.

Analyse the collected series with 1m intrabar order:

```bash
python scripts/analyze_1m_intrabar.py --data-dir /home/valarion/proteus-data/1m
```

Production run (2026-11-12): 20 newest signals, **143,280 bars**, **0 unfilled**, naive **+5.92R / PF 1.39 / DD 4.77R**, FSM **−4.08R / PF 0.63 / DD 5.90R**, **0/10** first-hit-order disagreements vs 1H. The FSM overlay hurts on this subset as well.

**Retention limit (verified 2026-11-12):** Bitget's public `history-candles` endpoint returned 1m data for the newest signal (LIT, 7,164 bars) but **zero rows for a 2026-09-04 window**. The old 95-signal corpus cannot be backfilled from this API. Choose one:

1. Run the fetcher continuously from now on (forward-only corpus; the daemon's `shadow_detections.jsonl` supplies the timestamps).
2. Buy/obtain a historical 1m archive for the venue (Bitget support, Tardis, CoinAPI, or a venue-specific archive) and store it in the same schema.
3. Accept 1H resolution and label every P&L as a bound, not a point estimate.

## 3. Chart labels

There are 284 images and 0 human bounding boxes. The current detector is a filled-rectangle color mask; it cannot be validated without labels.

Required: 500–2,000 labelled images (bounding boxes for TP/SL projection boxes and S/R zones). Recommended workflow:

1. Start with the 284 existing images; label the visible TP/SL boxes and the S/R zones.
2. Add 216+ new screenshots across different themes/symbols until the labelled set reaches ~500.
3. Store `human_profit_box`, `human_stop_box`, `human_sr_boxes` per image in a new corpus file; do not overwrite `vision_annotations.json` (it is legacy detector output).
4. Compute IoU only where a human box exists; report `None` elsewhere (the extractor now does this).

## 4. Paired detection timestamps

`ForwardShadowScanner` appends every non-abstain scan to `shadow_detections.jsonl`:

```json
{"symbol":"WLD","detected_at_utc":"2026-11-12T03:50:00+00:00","action":"ENTER_LONG","entry_price":"2.00","stop_loss":"1.95","take_profit":"2.20","confidence":0.84}
```

`ShadowLeadTimeComparator` pairs canonical signals with the closest detection in `[human − 6h, human + 1h]`. The metric remains `UNMEASURED` until forward detections and human posts overlap.

## 5. Funding, open interest, basis, order flow

Not present in any current file. Needed for the missing lenses in `docs/AUDIT-2026-11-10.md`:

| Dataset | Venue endpoint | Use |
|---|---|---|
| Funding rate history | Bitget `/api/v2/mix/market/history-fund-rate` | 48h hold cost |
| Open interest | Bitget `/api/v2/mix/market/open-interest` | crowding / squeeze context |
| Basis / mark price | Bitget mark-price candles | execution realism |
| Trades / order book | Bitget public trades + depth snapshots | CVD, absorption, queue |

Store each as a per-signal column keyed by `signal_id` and timestamp; do not synthesize missing values.

## 6. Acceptance gates before tuning

Do not fit another parameter until all of these are true:

- Chronological OOS recall and precision are reported together; current OOS is `1/21` recall with 26 false entries.
- Fill policy is explicit (`assume` vs `touch`); current touch-fill FSM is `−19.33R / PF 0.50`.
- At least two BTC regimes and ≥100 resolved trades per regime.
- Human labels exist for the vision set, or the vision component is removed from BPS.
- Every metric is computed from `PROTEUS_STATE_DIR` runtime state, never from checked-in benchmark JSON.
