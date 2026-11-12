"""Full-Detailed Project Proteus Web UI & JSON Telemetry Server (`proteus.web`)."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proteus.backtest import LifecycleBacktestSimulator
from proteus.constitution import (
    CONSTITUTIONAL_CORRIDORS,
    BoundedSelfCorrector,
    ConstitutionalIdentityGuard,
)
from proteus.evolver import AgenticSelfImprover
from proteus.geometry.fractal import FractalHorizontalStructureEngine
from proteus.market.lakehouse import NegativeSpaceDatasetBuilder
from proteus.monitor import SelfMonitoringWatchdog
from proteus.paper import VirtualPaperExchange
from proteus.paths import state_path
from proteus.policy.bayesian import BayesianCognitivePolicy, evaluate_time_split
from proteus.replay import EmpiricalCorpusReplay
from proteus.shadow.lead_time import ShadowLeadTimeComparator
from proteus.vision.chart_extractor import VisionCorpusAnalyzer

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "benchmarks" / "corpus"


def build_dashboard_payload(*, persist: bool = True) -> dict[str, Any]:
    """Assemble the complete, high-density telemetry payload for the Web UI.

    ``persist=False`` makes every GET path side-effect free: the watchdog is
    evaluated without saving its latch state, the self-improver never bootstraps,
    and the lead-time comparator only reads.
    """
    pure_codebase, scanned_files = ConstitutionalIdentityGuard.verify_codebase_purity()
    corrector = BoundedSelfCorrector()
    active_const = corrector.load_active_parameters(seed=persist)

    mon_snapshot = SelfMonitoringWatchdog().evaluate_and_heal(persist=persist)
    improver = AgenticSelfImprover()
    journal_rows = improver.load_journal()
    if not journal_rows and persist:
        improver.run_improvement_cycle(trigger_source="initial_bootstrap")
        journal_rows = improver.load_journal()
    chain_valid, chain_len = improver.verify_journal_hash_chain()

    replay_report = EmpiricalCorpusReplay().run()
    fractal_blind = FractalHorizontalStructureEngine().evaluate_real_corpus_blind_recall()
    dataset = NegativeSpaceDatasetBuilder().build_dataset(negative_count=5000)
    bayes_metrics = BayesianCognitivePolicy().fit(dataset).evaluate_dataset(dataset)
    oos_metrics = evaluate_time_split(dataset)
    backtest_report = LifecycleBacktestSimulator().run_comparative_backtest()
    vision_summary = VisionCorpusAnalyzer.summarize_corpus()
    lead_time = ShadowLeadTimeComparator().evaluate_shadow_lead_time(persist=persist)

    exchange = VirtualPaperExchange()
    hist_paper = exchange.run_historical_paper_simulation()

    snap_path = state_path("live_shadow_snapshot.json", seed=False)
    live_shadow: dict[str, Any] = (
        json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    )

    ledger_path = state_path("paper_ledger.json", seed=False)
    paper_ledger: dict[str, Any] = (
        json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    )

    signals: list[dict[str, Any]] = json.loads(
        (CORPUS_DIR / "canonical_signals.json").read_text(encoding="utf-8")
    )
    updates: list[dict[str, Any]] = json.loads(
        (CORPUS_DIR / "management_updates.json").read_text(encoding="utf-8")
    )
    trajectories: list[dict[str, Any]] = json.loads(
        (CORPUS_DIR / "signal_candle_trajectories.json").read_text(encoding="utf-8")
    )
    vision_rows: list[dict[str, Any]] = json.loads(
        (CORPUS_DIR / "vision_annotations.json").read_text(encoding="utf-8")
    )

    traj_by_id = {t["signal_id"]: t for t in trajectories}
    enriched_signals: list[dict[str, Any]] = []
    for s in signals:
        entry = float(s["entry_price"])
        sl = float(s["stop_loss"])
        risk = abs(entry - sl)
        risk_pct = round((risk / entry) * 100.0, 2) if entry > 0 else 0.0
        tps = s.get("take_profits") or []
        tp1 = tps[0] if tps else None
        rr = round(abs(float(tp1) - entry) / risk, 2) if (tp1 and risk > 0) else None
        tr = traj_by_id.get(s["id"], {})
        enriched_signals.append(
            {
                "telegram_msg_num": s.get("telegram_msg_num"),
                "received_at": s.get("received_at") or s.get("created_at"),
                "symbol": s["pair_token"].replace("USDT", "").upper(),
                "direction": s["direction"],
                "entry_price": s["entry_price"],
                "stop_loss": s["stop_loss"],
                "risk_pct": risk_pct,
                "take_profit_1": tp1,
                "target_count": len(tps),
                "planned_rr": rr,
                "mfe_r_48h": tr.get("mfe_r_48h"),
                "mae_r_48h": tr.get("mae_r_48h"),
                "first_hit_1r_min": tr.get("first_hit_1r_min"),
                "first_hit_sl_min": tr.get("first_hit_sl_min"),
                "has_media": s.get("has_media", False),
                "raw_text": (s.get("raw_text") or "")[:240],
            }
        )

    corridors_view = [
        {
            "parameter": k,
            "min_allowed": low,
            "anchor_prior": anchor,
            "max_allowed": high,
            "active_value": getattr(active_const, k),
        }
        for k, (low, anchor, high) in CONSTITUTIONAL_CORRIDORS.items()
    ]

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "self_monitor": mon_snapshot.to_dict(),
        "self_improver": {
            "hash_chain_valid": chain_valid,
            "journal_length": chain_len,
            "journal": list(reversed(journal_rows[-20:])),
        },
        "constitution": {
            "pure_codebase": pure_codebase,
            "scanned_source_files": scanned_files,
            "active_generation": active_const.generation,
            "active_parameters": active_const.to_dict(),
            "corridors": corridors_view,
        },
        "turing_replay": dataclasses.asdict(replay_report),
        "fractal_blind_recall": fractal_blind.to_dict(),
        "bayesian_5097": dataclasses.asdict(bayes_metrics),
        "bayesian_oos_time_split": (
            dataclasses.asdict(oos_metrics) if oos_metrics is not None else None
        ),
        "comparative_backtest": dataclasses.asdict(backtest_report),
        "historical_paper_sim": hist_paper,
        "live_shadow": live_shadow,
        "paper_ledger": paper_ledger,
        "lead_time_summary": {
            "evaluated_pairs": lead_time.evaluated_pairs,
            "median_delta_t_seconds": lead_time.median_delta_t_seconds,
            "mean_delta_t_seconds": lead_time.mean_delta_t_seconds,
            "front_run_or_simultaneous_rate_pct": lead_time.front_run_or_simultaneous_rate_pct,
            "recent_comparisons": [dataclasses.asdict(c) for c in lead_time.comparisons[-15:]],
        },
        "vision_summary": dataclasses.asdict(vision_summary),
        "vision_samples": vision_rows[:60],
        "signals_ledger": list(reversed(enriched_signals)),
        "management_updates": list(reversed(updates)),
    }
