"""Phase 4: Candle-driven autonomous trade backtest (`proteus.backtest`).

Every P&L number is now derived from the real Bitget 1H candles in
`benchmarks/corpus/real_1h_candles_by_signal.json`. There are no hash draws,
no loop-index coin flips, and no Telegram-keyword-to-fixed-R mappings.

Intrabar policy (1H OHLC cannot resolve order):
- ``conservative`` (default): if stop and target are both touched inside one
  bar, the stop is assumed first. This understates the FSM benefit.
- ``favorable``: target first. Reported only as a sensitivity bound.

The FSM is the same contract as ``proteus.fsm``: move the stop to entry at
+1.0R and book 50% at +1.5R. Fees are charged once per round trip as a fraction
of R (Bitget maker 2 bps entry + taker 6 bps exit by default).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "corpus"

DEFAULT_ROUND_TRIP_FEE_PCT = 0.0008  # 2 bps maker + 6 bps taker


@dataclass(frozen=True)
class RegimePerformance:
    regime_name: str
    total_trades: int
    wins: int
    breakeven_scratches: int
    losses: int
    win_rate_pct: float
    scratch_rate_pct: float
    loss_rate_pct: float
    total_realized_r: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    total_fees_r: float = 0.0


@dataclass(frozen=True)
class RealCandleForensicAudit:
    resolved_signals: int
    reached_1r_before_sl: int
    reached_1r_pct: float
    whipsaw_reversed_to_sl_after_1r: int
    whipsaw_rate_of_1r_winners_pct: float
    hit_sl_first_before_1r: int
    hit_sl_first_pct: float
    silent_telegram_when_sl_first: int
    silent_telegram_when_1r_reached: int
    silent_stop_out_share_pct: float


@dataclass(frozen=True)
class ComparativeBacktestReport:
    naive_set_and_forget: RegimePerformance
    proteus_distilled_fsm: RegimePerformance
    proteus_alpha_edge_r: float
    drawdown_reduction_r: float
    real_candle_audit: RealCandleForensicAudit
    resolution: str = "1H"
    intrabar_policy: str = "conservative"
    fee_model: str = "bitget_maker_2bps+taker_6bps"
    unresolved_signals: int = 0
    notes: str = ""


class LifecycleBacktestSimulator:
    """Simulates every resolvable setup on its real Bitget 1H post-entry candles."""

    def __init__(
        self,
        corpus_dir: Path | None = None,
        round_trip_fee_pct: float = DEFAULT_ROUND_TRIP_FEE_PCT,
        intrabar_policy: Literal["conservative", "favorable"] = "conservative",
    ) -> None:
        self.corpus_dir = corpus_dir or DEFAULT_CORPUS_DIR
        self.round_trip_fee_pct = max(0.0, float(round_trip_fee_pct))
        self.intrabar_policy = intrabar_policy

    # -- statistics ---------------------------------------------------------

    @staticmethod
    def _compute_stats(name: str, r_series: list[float], fees_r: float = 0.0) -> RegimePerformance:
        wins = sum(1 for r in r_series if r > 0.05)
        scratches = sum(1 for r in r_series if -0.05 <= r <= 0.05)
        losses = sum(1 for r in r_series if r < -0.05)
        n = max(1, len(r_series))

        gross_profit = sum(r for r in r_series if r > 0.0)
        gross_loss = abs(sum(r for r in r_series if r < 0.0))
        profit_factor = round(gross_profit / max(0.01, gross_loss), 2)

        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in r_series:
            equity += r
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        total_r = round(sum(r_series), 2)
        return RegimePerformance(
            regime_name=name,
            total_trades=len(r_series),
            wins=wins,
            breakeven_scratches=scratches,
            losses=losses,
            win_rate_pct=round((wins / n) * 100.0, 1),
            scratch_rate_pct=round((scratches / n) * 100.0, 1),
            loss_rate_pct=round((losses / n) * 100.0, 1),
            total_realized_r=total_r,
            expectancy_r=round(total_r / n, 2),
            profit_factor=profit_factor,
            max_drawdown_r=round(max_dd, 2),
            total_fees_r=round(fees_r, 2),
        )

    # -- simulation ---------------------------------------------------------

    def _simulate(
        self,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        bars: list[list[float]],
        use_fsm: bool,
    ) -> float:
        """Return realized R from the post-entry 1H bars.

        Conservative intrabar rule: when a bar touches both the stop and any
        favorable level, the stop is assumed to have been hit first.
        """
        risk = abs(entry - stop_loss)
        if risk <= 0.0 or not bars:
            return 0.0

        is_long = direction == "LONG"
        cur_sl = stop_loss
        remaining = 1.0
        realized = 0.0
        be_done = False
        tp1_done = False

        def r_of(price: float) -> float:
            return ((price - entry) / risk) if is_long else ((entry - price) / risk)

        for row in bars:
            high = float(row[2])
            low = float(row[3])
            close = float(row[4])

            if is_long:
                sl_hit = low <= cur_sl
                tp_hit = high >= take_profit
                hit_1r = high >= entry + risk
                hit_15r = high >= entry + 1.5 * risk
            else:
                sl_hit = high >= cur_sl
                tp_hit = low <= take_profit
                hit_1r = low <= entry - risk
                hit_15r = low <= entry - 1.5 * risk

            if self.intrabar_policy == "conservative":
                if sl_hit:
                    realized += remaining * r_of(cur_sl)
                    return realized

            if use_fsm:
                if hit_15r and not tp1_done:
                    realized += 0.5 * 1.5
                    remaining = 0.5
                    cur_sl = entry
                    be_done = True
                    tp1_done = True
                elif hit_1r and not be_done:
                    cur_sl = entry
                    be_done = True

            if tp_hit:
                realized += remaining * r_of(take_profit)
                return realized

            if self.intrabar_policy == "favorable":
                # Re-check the stop against the possibly-moved breakeven level.
                if is_long:
                    sl_now = low <= cur_sl
                else:
                    sl_now = high >= cur_sl
                if sl_now:
                    realized += remaining * r_of(cur_sl)
                    return realized

        # No exit: mark the remaining position at the last close.
        realized += remaining * r_of(float(bars[-1][4]))
        return realized

    def _fee_r(self, entry: float, risk: float) -> float:
        if risk <= 0.0:
            return 0.0
        return (entry / risk) * self.round_trip_fee_pct

    # -- corpus -------------------------------------------------------------

    def _load(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
        signals = json.loads(
            (self.corpus_dir / "canonical_signals.json").read_text(encoding="utf-8")
        )
        trajectories = json.loads(
            (self.corpus_dir / "signal_candle_trajectories.json").read_text(encoding="utf-8")
        )
        candles = json.loads(
            (self.corpus_dir / "real_1h_candles_by_signal.json").read_text(encoding="utf-8")
        )
        return signals, trajectories, {row["signal_id"]: row for row in candles}

    @staticmethod
    def _telegram_mentions(signals: list[dict[str, Any]], messages: list[dict[str, Any]]) -> dict[str, bool]:
        """Did the human post any follow-up about this signal within 7 days?"""
        msgs_sorted = sorted(messages, key=lambda m: m["received_at"])
        mentioned: dict[str, bool] = {}
        for sig in signals:
            tok = sig["pair_token"].replace("USDT", "").upper()
            s_dt = datetime.fromisoformat(sig["received_at"] or sig["created_at"])
            found = False
            for m in msgs_sorted:
                m_dt = datetime.fromisoformat(m["received_at"])
                delta_s = (m_dt - s_dt).total_seconds()
                if not (0 < delta_s <= 7 * 86400):
                    continue
                txt = (m.get("raw_text") or "").lower()
                if (
                    f"${tok.lower()}" in txt
                    or f"#{tok.lower()}" in txt
                    or re.search(rf"\b{re.escape(tok.lower())}\b", txt)
                ):
                    if any(
                        k in txt
                        for k in (
                            "full tp",
                            "tp1",
                            "booked",
                            "took profit",
                            "sl to entry",
                            "stoploss to entry",
                            "hit sl",
                            "invalidation",
                            "stopped",
                            "took a loss",
                            "closed",
                            "sleep",
                        )
                    ):
                        found = True
                        break
            mentioned[sig["id"]] = found
        return mentioned

    def run_comparative_backtest(self) -> ComparativeBacktestReport:
        signals, trajectories, candles_by_id = self._load()
        messages = json.loads(
            (self.corpus_dir / "telegram_messages.json").read_text(encoding="utf-8")
        )
        traj_by_id = {t["signal_id"]: t for t in trajectories}
        mentioned = self._telegram_mentions(signals, messages)

        naive_r: list[float] = []
        proteus_r: list[float] = []
        fees_r = 0.0
        unresolved = 0

        for sig in sorted(signals, key=lambda s: s["received_at"] or s["created_at"]):
            row = candles_by_id.get(sig["id"])
            bars = (row or {}).get("post_48h_candles") or []
            if not bars or not (row or {}).get("stop_loss_scaled"):
                unresolved += 1
                continue

            direction = sig["direction"]
            entry = float(row["entry_price_scaled"])
            stop_loss = float(row["stop_loss_scaled"])
            risk = abs(entry - stop_loss)
            if risk <= 0.0:
                unresolved += 1
                continue

            scale = float(row.get("scale_applied") or 1.0)
            tps = sig.get("take_profits") or []
            if tps:
                take_profit = float(tps[0]) * scale
            else:
                take_profit = entry + 4.56 * risk if direction == "LONG" else entry - 4.56 * risk

            if (direction == "LONG" and take_profit <= entry) or (
                direction == "SHORT" and take_profit >= entry
            ):
                take_profit = entry + 4.56 * risk if direction == "LONG" else entry - 4.56 * risk

            fee_r = self._fee_r(entry, risk)
            fees_r += fee_r

            naive_r.append(
                round(self._simulate(direction, entry, stop_loss, take_profit, bars, False) - fee_r, 4)
            )
            proteus_r.append(
                round(self._simulate(direction, entry, stop_loss, take_profit, bars, True) - fee_r, 4)
            )

        naive_perf = self._compute_stats(
            "Naive Set-and-Forget (no in-flight FSM)", naive_r, fees_r
        )
        proteus_perf = self._compute_stats(
            "Project Proteus FSM (+1R BE, 50% at +1.5R)", proteus_r, fees_r
        )

        # Forensic audit (no P&L): real candle first-hit ordering + Telegram silence.
        resolved_count = 0
        reached_1r_count = 0
        whipsaw_count = 0
        sl_first_count = 0
        silent_sl_first = 0
        silent_1r = 0

        for sig in signals:
            tr = traj_by_id.get(sig["id"])
            if not tr or not tr.get("post_48h_bars"):
                continue
            resolved_count += 1
            t_1r = tr.get("first_hit_1r_min")
            t_sl = tr.get("first_hit_sl_min")
            if t_1r is not None and (t_sl is None or t_1r <= t_sl):
                reached_1r_count += 1
                if t_sl is not None and t_1r < t_sl:
                    whipsaw_count += 1
                if not mentioned.get(sig["id"], False):
                    silent_1r += 1
            elif t_sl is not None and (t_1r is None or t_sl < t_1r):
                sl_first_count += 1
                if not mentioned.get(sig["id"], False):
                    silent_sl_first += 1

        total_silent_resolved = max(1, silent_sl_first + silent_1r)
        audit = RealCandleForensicAudit(
            resolved_signals=resolved_count,
            reached_1r_before_sl=reached_1r_count,
            reached_1r_pct=round((reached_1r_count / max(1, resolved_count)) * 100.0, 1),
            whipsaw_reversed_to_sl_after_1r=whipsaw_count,
            whipsaw_rate_of_1r_winners_pct=round(
                (whipsaw_count / max(1, reached_1r_count)) * 100.0, 1
            ),
            hit_sl_first_before_1r=sl_first_count,
            hit_sl_first_pct=round((sl_first_count / max(1, resolved_count)) * 100.0, 1),
            silent_telegram_when_sl_first=silent_sl_first,
            silent_telegram_when_1r_reached=silent_1r,
            silent_stop_out_share_pct=round(
                (silent_sl_first / total_silent_resolved) * 100.0, 1
            ),
        )

        return ComparativeBacktestReport(
            naive_set_and_forget=naive_perf,
            proteus_distilled_fsm=proteus_perf,
            proteus_alpha_edge_r=round(
                proteus_perf.total_realized_r - naive_perf.total_realized_r, 2
            ),
            drawdown_reduction_r=round(
                naive_perf.max_drawdown_r - proteus_perf.max_drawdown_r, 2
            ),
            real_candle_audit=audit,
            intrabar_policy=self.intrabar_policy,
            unresolved_signals=unresolved,
            notes=(
                "P&L is simulated from real Bitget 1H post-entry candles only. "
                "1H OHLC cannot resolve intrabar order; conservative policy is used."
            ),
        )
