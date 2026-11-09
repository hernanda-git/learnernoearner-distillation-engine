#!/usr/bin/env python3
"""Run the complete Project Proteus Phases 1-4 Cognitive Turing & Backtest Suite."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.backtest import LifecycleBacktestSimulator  # noqa: E402
from proteus.market.lakehouse import NegativeSpaceDatasetBuilder  # noqa: E402
from proteus.policy.bayesian import BayesianCognitivePolicy  # noqa: E402
from proteus.replay import EmpiricalCorpusReplay  # noqa: E402


def main() -> int:
    replay_report = EmpiricalCorpusReplay().run()
    dataset = NegativeSpaceDatasetBuilder().build_dataset(negative_count=5000)
    bayesian_metrics = BayesianCognitivePolicy().fit(dataset).evaluate_dataset(dataset)
    backtest_report = LifecycleBacktestSimulator().run_comparative_backtest()

    summary = {
        "corpus_replay": dataclasses.asdict(replay_report),
        "bayesian_policy_5097_bars": dataclasses.asdict(bayesian_metrics),
        "comparative_backtest_97_setups": dataclasses.asdict(backtest_report),
    }
    print(json.dumps(summary, indent=2))
    return 0 if replay_report.parity_metrics.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
