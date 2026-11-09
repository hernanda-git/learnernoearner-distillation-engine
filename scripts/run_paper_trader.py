#!/usr/bin/env python3
"""Autonomous Virtual Paper Trading CLI (`scripts/run_paper_trader.py`).

Supports three operational modes:
  1. `--mode live-step`   : Scan live Bitget public candles (or cached snapshot) and step the virtual ledger once.
  2. `--mode historical`  : Simulate a $1,000 USDT paper account across all 97 historical signals.
  3. `--mode daemon`      : Run continuous 24/7 live paper trading with Self-Monitoring Watchdog & AI Self-Improvement.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.evolver import AgenticSelfImprover  # noqa: E402
from proteus.monitor import SelfMonitoringWatchdog  # noqa: E402
from proteus.paper import VirtualPaperExchange  # noqa: E402
from proteus.shadow import AssetShadowState, ForwardShadowScanner, LiveShadowSnapshot  # noqa: E402


def _load_or_scan_snapshot(refresh_live: bool) -> LiveShadowSnapshot:
    snapshot_path = REPO_ROOT / "benchmarks" / "live_shadow_snapshot.json"
    if not refresh_live and snapshot_path.exists():
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
        states = [AssetShadowState(**s) for s in raw["states"]]
        return LiveShadowSnapshot(
            scanned_at_utc=raw["scanned_at_utc"],
            btc_1d_close=raw["btc_1d_close"],
            eth_1d_close=raw["eth_1d_close"],
            macro_regime=raw["macro_regime"],
            universe_evaluated=raw["universe_evaluated"],
            active_entries=raw["active_entries"],
            abstentions=raw["abstentions"],
            states=states,
        )
    scanner = ForwardShadowScanner()
    snapshot = scanner.scan_live_universe()
    snapshot_path.write_text(json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project Proteus Autonomous Virtual Paper Trading Simulator"
    )
    parser.add_argument(
        "--mode",
        choices=("live-step", "historical", "daemon"),
        default="live-step",
        help="Execution mode: live-step (default), historical (97-signal simulation), or daemon (continuous loop).",
    )
    parser.add_argument(
        "--refresh-live",
        action="store_true",
        help="Fetch fresh public candles from Bitget before stepping the paper ledger.",
    )
    parser.add_argument(
        "--equity",
        type=float,
        default=1000.0,
        help="Starting synthetic paper equity in USDT (default: 1000.0).",
    )
    parser.add_argument(
        "--risk-usdt",
        type=float,
        default=20.0,
        help="Capital risk per 1.0R trade in USDT (default: 20.0 = 2.0%%).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds for --mode daemon (default: 300s / 5m).",
    )
    args = parser.parse_args(argv)

    exchange = VirtualPaperExchange(
        starting_equity_usdt=args.equity,
        risk_per_trade_usdt=args.risk_usdt,
    )

    if args.mode == "historical":
        result = exchange.run_historical_paper_simulation()
        print(json.dumps(result, indent=2))
        return 0

    if args.mode == "live-step":
        snapshot = _load_or_scan_snapshot(refresh_live=args.refresh_live)
        ledger = exchange.process_shadow_snapshot(snapshot)
        SelfMonitoringWatchdog().evaluate_and_heal()
        print(json.dumps(ledger.to_dict(), indent=2))
        return 0

    watchdog = SelfMonitoringWatchdog()
    improver = AgenticSelfImprover(watchdog=watchdog)
    cycle_idx = 0
    while True:
        snapshot = _load_or_scan_snapshot(refresh_live=True)
        ledger = exchange.process_shadow_snapshot(snapshot)
        mon = watchdog.evaluate_and_heal()
        if cycle_idx % 12 == 0:
            improver.run_improvement_cycle(trigger_source="daemon_hourly_auto_evolve")
        cycle_idx += 1
        print(
            json.dumps(
                {
                    "scanned_at_utc": snapshot.scanned_at_utc,
                    "macro_regime": snapshot.macro_regime,
                    "current_equity_usdt": ledger.current_equity_usdt,
                    "open_positions": ledger.open_positions_count,
                    "monitor_status": mon.overall_status,
                    "healthy_streak": mon.consecutive_healthy_cycles,
                }
            ),
            flush=True,
        )
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
