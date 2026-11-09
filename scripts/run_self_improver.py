#!/usr/bin/env python3
"""Run the Project Proteus Self-Monitoring Watchdog & 4-Stage AI-Agent Self-Improver."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.evolver import AgenticSelfImprover  # noqa: E402
from proteus.monitor import SelfMonitoringWatchdog  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project Proteus Self-Monitoring Watchdog & AI-Agent Self-Improver"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.12,
        help="Prior-anchored Bayesian shrinkage rate alpha in [0.05, 0.25] (default: 0.12).",
    )
    args = parser.parse_args(argv)

    watchdog = SelfMonitoringWatchdog()
    monitor_snapshot = watchdog.evaluate_and_heal()

    improver = AgenticSelfImprover(watchdog=watchdog)
    entry = improver.run_improvement_cycle(
        trigger_source="cli_self_improver",
        learning_rate=args.learning_rate,
    )
    chain_valid, chain_len = improver.verify_journal_hash_chain()

    print(
        json.dumps(
            {
                "self_monitor": monitor_snapshot.to_dict(),
                "improvement_entry": entry.to_dict(),
                "hash_chain_verified": chain_valid,
                "journal_length": chain_len,
            },
            indent=2,
        )
    )
    return 0 if chain_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
