#!/usr/bin/env python3
"""Run the complete Project Proteus Phases 1-6 Cognitive Turing & Constitutional Suite."""

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
from proteus.constitution import BoundedSelfCorrector, ConstitutionalIdentityGuard  # noqa: E402
from proteus.market.lakehouse import NegativeSpaceDatasetBuilder  # noqa: E402
from proteus.paper import VirtualPaperExchange  # noqa: E402
from proteus.policy.bayesian import BayesianCognitivePolicy  # noqa: E402
from proteus.replay import EmpiricalCorpusReplay  # noqa: E402
from proteus.shadow.lead_time import ShadowLeadTimeComparator  # noqa: E402
from proteus.vision.chart_extractor import VisionCorpusAnalyzer  # noqa: E402


def main() -> int:
    pure_codebase, scanned_py_files = ConstitutionalIdentityGuard.verify_codebase_purity()
    active_constitution = BoundedSelfCorrector().load_active_parameters()
    replay_report = EmpiricalCorpusReplay().run()
    dataset = NegativeSpaceDatasetBuilder().build_dataset(negative_count=5000)
    bayesian_metrics = BayesianCognitivePolicy().fit(dataset).evaluate_dataset(dataset)
    backtest_report = LifecycleBacktestSimulator().run_comparative_backtest()
    vision_summary = VisionCorpusAnalyzer.summarize_corpus()
    lead_time_summary = ShadowLeadTimeComparator().evaluate_shadow_lead_time()
    paper_sim = VirtualPaperExchange().run_historical_paper_simulation()

    summary = {
        "validated": replay_report.parity_metrics.passed,
        "unmeasured_components": list(replay_report.parity_metrics.unmeasured),
        "constitutional_identity_guard": {
            "codebase_anti_indicator_purity": pure_codebase,
            "scanned_source_files": scanned_py_files,
            "active_generation": active_constitution.generation,
            "active_parameters": active_constitution.to_dict(),
        },
        "phase1_and_3_bayesian_policy_5091_bars": dataclasses.asdict(bayesian_metrics),
        "phase2_vision_corpus_284_charts": dataclasses.asdict(vision_summary),
        "phase4_corpus_replay_turing_scorecard": dataclasses.asdict(replay_report),
        "phase4_candle_backtest_91_setups": dataclasses.asdict(backtest_report),
        "phase6_shadow_lead_time_parity": {
            "evaluated_pairs": lead_time_summary.evaluated_pairs,
            "median_delta_t_seconds": lead_time_summary.median_delta_t_seconds,
            "mean_delta_t_seconds": lead_time_summary.mean_delta_t_seconds,
            "front_run_or_simultaneous_rate_pct": lead_time_summary.front_run_or_simultaneous_rate_pct,
        },
        "phase6_fee_adjusted_paper_simulation": paper_sim,
    }
    print(json.dumps(summary, indent=2))
    return 0 if pure_codebase else 1


if __name__ == "__main__":
    raise SystemExit(main())
