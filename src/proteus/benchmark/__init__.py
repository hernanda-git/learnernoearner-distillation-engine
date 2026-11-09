"""Cognitive Turing Validation & Behavioral Parity Scorecard (`proteus.benchmark`).

Evaluates the Behavioral Parity Score (BPS) from docs/MASTER-PLAN.md Phase 4:
    BPS = 0.35 * S_action + 0.25 * S_spatial + 0.25 * S_abstain + 0.15 * S_timing
and verifies all 6 Acceptance Metric Matrix thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParityMetrics:
    directional_concordance: float
    setup_recall: float
    spatial_iou: float
    abstention_accuracy: float
    sl_proximity_delta_pct: float
    tp_proximity_delta_pct: float
    median_timing_delta_seconds: float
    bps: float
    passed: bool


class BehavioralParityBenchmark:
    """Computes Behavioral Parity Score (BPS) and acceptance gates."""

    BPS_ACCEPTANCE_THRESHOLD: float = 0.85

    @classmethod
    def evaluate(
        cls,
        *,
        directional_concordance: float,
        setup_recall: float,
        spatial_iou: float,
        abstention_accuracy: float,
        sl_proximity_delta_pct: float,
        tp_proximity_delta_pct: float,
        median_timing_delta_seconds: float,
    ) -> ParityMetrics:
        s_action = 0.5 * directional_concordance + 0.5 * setup_recall
        s_spatial = spatial_iou
        s_abstain = abstention_accuracy
        # Timing score: 1.0 when delta <= 0s (before or simultaneous with human alert),
        # decaying linearly to 0.0 at +60s delay.
        if median_timing_delta_seconds <= 0.0:
            s_timing = 1.0
        elif median_timing_delta_seconds >= 60.0:
            s_timing = 0.0
        else:
            s_timing = 1.0 - (median_timing_delta_seconds / 60.0)

        bps = round(
            0.35 * s_action + 0.25 * s_spatial + 0.25 * s_abstain + 0.15 * s_timing,
            4,
        )

        gates_passed = (
            directional_concordance >= 0.90
            and setup_recall >= 0.75
            and spatial_iou >= 0.80
            and abstention_accuracy >= 0.95
            and sl_proximity_delta_pct <= 0.50
            and tp_proximity_delta_pct <= 1.00
            and median_timing_delta_seconds <= 0.0
            and bps >= cls.BPS_ACCEPTANCE_THRESHOLD
        )

        return ParityMetrics(
            directional_concordance=directional_concordance,
            setup_recall=setup_recall,
            spatial_iou=spatial_iou,
            abstention_accuracy=abstention_accuracy,
            sl_proximity_delta_pct=sl_proximity_delta_pct,
            tp_proximity_delta_pct=tp_proximity_delta_pct,
            median_timing_delta_seconds=median_timing_delta_seconds,
            bps=bps,
            passed=gates_passed,
        )
