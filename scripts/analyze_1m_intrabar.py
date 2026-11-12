#!/usr/bin/env python3
"""Analyse 1-minute candles for the signals that have a forward-retained series.

This is the evidence check the 1H backtest cannot perform: it replays the same
FSM with 1m intrabar order, measures how often the 1H conservative assumption
disagrees with the 1m first-hit order, and reports the fill sensitivity.

Usage:
    python scripts/analyze_1m_intrabar.py --data-dir /home/valarion/proteus-data/1m
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = REPO_ROOT / "benchmarks" / "corpus"
ROUND_TRIP_FEE_PCT = 0.0008


def _stats(series: list[float]) -> dict[str, float]:
    wins = sum(1 for value in series if value > 0.05)
    scratches = sum(1 for value in series if -0.05 <= value <= 0.05)
    losses = sum(1 for value in series if value < -0.05)
    gross_profit = sum(value for value in series if value > 0)
    gross_loss = abs(sum(value for value in series if value < 0))
    equity = peak = drawdown = 0.0
    for value in series:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(series),
        "wins": wins,
        "scratches": scratches,
        "losses": losses,
        "win_rate_pct": round(wins / max(1, len(series)) * 100.0, 1),
        "total_r": round(sum(series), 2),
        "profit_factor": round(gross_profit / max(0.01, gross_loss), 2),
        "max_drawdown_r": round(drawdown, 2),
    }


def _simulate(
    direction: str, entry: float, stop_loss: float, take_profit: float, bars: list[list[float]], use_fsm: bool
) -> float:
    risk = abs(entry - stop_loss)
    if risk <= 0 or not bars:
        return 0.0
    is_long = direction == "LONG"
    current_sl = stop_loss
    remaining = 1.0
    realized = 0.0
    breakeven = tp1 = False

    def r_of(price: float) -> float:
        return (price - entry) / risk if is_long else (entry - price) / risk

    def stop_hit(high: float, low: float) -> bool:
        return low <= current_sl if is_long else high >= current_sl

    def target_hit(high: float, low: float) -> bool:
        return high >= take_profit if is_long else low <= take_profit

    for _ts, _open, high, low, close, _volume in bars:
        high, low, close = float(high), float(low), float(close)
        if stop_hit(high, low):
            realized += remaining * r_of(current_sl)
            return realized
        if r_of(take_profit) < 1.5 and target_hit(high, low):
            realized += remaining * r_of(take_profit)
            return realized
        if use_fsm:
            hit_1r = high >= entry + risk if is_long else low <= entry - risk
            hit_15r = high >= entry + 1.5 * risk if is_long else low <= entry - 1.5 * risk
            if hit_15r and not tp1:
                realized += 0.5 * 1.5
                remaining = 0.5
                current_sl = entry
                breakeven = tp1 = True
            elif hit_1r and not breakeven:
                current_sl = entry
                breakeven = True
        if stop_hit(high, low):
            realized += remaining * r_of(current_sl)
            return realized
        if target_hit(high, low):
            realized += remaining * r_of(take_profit)
            return realized
    realized += remaining * r_of(float(bars[-1][4]))
    return realized


def _first_hits(entry: float, stop_loss: float, bars: list[list[float]], direction: str) -> tuple[int | None, int | None]:
    risk = abs(entry - stop_loss)
    long = direction == "LONG"
    first_1r = first_sl = None
    for index, (ts, _open, high, low, _close, _volume) in enumerate(bars):
        high, low = float(high), float(low)
        if first_1r is None and ((high >= entry + risk) if long else (low <= entry - risk)):
            first_1r = int(ts)
        if first_sl is None and ((low <= stop_loss) if long else (high >= stop_loss)):
            first_sl = int(ts)
        if first_1r is not None and first_sl is not None:
            break
    return first_1r, first_sl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args(argv)

    signals = {
        row["id"]: row
        for row in json.loads((args.corpus_dir / "canonical_signals.json").read_text(encoding="utf-8"))
    }
    candle_rows = {
        row["signal_id"]: row
        for row in json.loads(
            (args.corpus_dir / "real_1h_candles_by_signal.json").read_text(encoding="utf-8")
        )
    }
    trajectories = {
        row["signal_id"]: row
        for row in json.loads(
            (args.corpus_dir / "signal_candle_trajectories.json").read_text(encoding="utf-8")
        )
    }

    naive: list[float] = []
    fsm: list[float] = []
    unfilled = 0
    order_disagreements = 0
    order_checked = 0
    rows: list[dict[str, Any]] = []

    for path in sorted(args.data_dir.glob("*.json")):
        if path.name in {"MANIFEST.json", "ANALYSIS.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        signal = signals.get(payload.get("signal_id"))
        candle_row = candle_rows.get(payload.get("signal_id"))
        bars = payload.get("candles") or []
        t0_ms = candle_row.get("t0_ms") if candle_row else None
        if t0_ms is None:
            t0_ms = int(payload.get("start_ms", 0)) + 72 * 3600 * 1000
        bars = [row for row in bars if int(row[0]) >= int(t0_ms)]
        if signal is None or candle_row is None or not bars:
            continue
        direction = signal["direction"]
        entry = float(candle_row["entry_price_scaled"])
        stop_loss = float(candle_row["stop_loss_scaled"])
        risk = abs(entry - stop_loss)
        if risk <= 0:
            continue
        tps = signal.get("take_profits") or []
        fallback_rr = 4.87 if direction == "LONG" else 4.46
        take_profit = (
            float(tps[0]) * float(candle_row.get("scale_applied") or 1.0)
            if tps
            else entry + fallback_rr * risk if direction == "LONG" else entry - fallback_rr * risk
        )
        if (direction == "LONG" and take_profit <= entry) or (
            direction == "SHORT" and take_profit >= entry
        ):
            take_profit = entry + fallback_rr * risk if direction == "LONG" else entry - fallback_rr * risk

        fill_index = next(
            (
                index
                for index, row in enumerate(bars)
                if (
                    float(row[3]) <= entry
                    if direction == "LONG"
                    else float(row[2]) >= entry
                )
            ),
            None,
        )
        if fill_index is None:
            unfilled += 1
            continue
        entry_bars = bars[fill_index:]
        fee_r = (entry / risk) * ROUND_TRIP_FEE_PCT
        naive.append(_simulate(direction, entry, stop_loss, take_profit, entry_bars, False) - fee_r)
        fsm.append(_simulate(direction, entry, stop_loss, take_profit, entry_bars, True) - fee_r)

        first_1r_ms, first_sl_ms = _first_hits(entry, stop_loss, entry_bars, direction)
        trajectory = trajectories.get(payload["signal_id"], {})
        if first_1r_ms is not None and first_sl_ms is not None:
            one_m_1r_first = first_1r_ms < first_sl_ms
            one_h_1r = trajectory.get("first_hit_1r_min")
            one_h_sl = trajectory.get("first_hit_sl_min")
            if one_h_1r is not None and one_h_sl is not None:
                order_checked += 1
                if (one_m_1r_first) != (one_h_1r < one_h_sl):
                    order_disagreements += 1
        rows.append(
            {
                "signal_id": payload["signal_id"],
                "symbol": signal["pair_token"],
                "telegram_msg_num": signal.get("telegram_msg_num"),
                "bars_1m": len(entry_bars),
                "entry_at_ms": int(entry_bars[0][0]),
                "naive_r": round(naive[-1], 4),
                "fsm_r": round(fsm[-1], 4),
                "first_1r_ms": first_1r_ms,
                "first_sl_ms": first_sl_ms,
            }
        )

    result = {
        "signals_with_1m": len(rows),
        "unfilled": unfilled,
        "naive": _stats(naive),
        "fsm": _stats(fsm),
        "first_hit_order_checked": order_checked,
        "first_hit_order_disagreements_vs_1h": order_disagreements,
        "rows": rows,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
