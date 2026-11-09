"""Cognitive Turing validation & Behavioral Parity Scorecard (`proteus.benchmark`).

BPS is only computed when every component is actually measured. A missing
component (for example, no human bounding-box labels for vision, or no logged
detection timestamps for lead time) returns ``bps=None`` and ``passed=False``
instead of silently substituting a constant.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParityMetrics:
    directional_concordance: float | None
    setup_recall: float
    spatial_iou: float | None
    abstention_accuracy: float | None
    sl_proximity_delta_pct: float
    tp_proximity_delta_pct: float
    median_timing_delta_seconds: float | None
    bps: float | None
    passed: bool
    unmeasured: tuple[str, ...] = ()


class BehavioralParityBenchmark:
    """Computes Behavioral Parity Score (BPS) and acceptance gates."""

    BPS_ACCEPTANCE_THRESHOLD: float = 0.85

    @classmethod
    def evaluate(
        cls,
        *,
        directional_concordance: float | None,
        setup_recall: float,
        spatial_iou: float | None,
        abstention_accuracy: float | None,
        sl_proximity_delta_pct: float,
        tp_proximity_delta_pct: float,
        median_timing_delta_seconds: float | None,
    ) -> ParityMetrics:
        unmeasured: list[str] = []
        if directional_concordance is None:
            unmeasured.append("directional_concordance")
        if spatial_iou is None:
            unmeasured.append("spatial_iou")
        if abstention_accuracy is None:
            unmeasured.append("abstention_accuracy")
        if median_timing_delta_seconds is None:
            unmeasured.append("median_timing_delta_seconds")

        if unmeasured:
            return ParityMetrics(
                directional_concordance=directional_concordance,
                setup_recall=setup_recall,
                spatial_iou=spatial_iou,
                abstention_accuracy=abstention_accuracy,
                sl_proximity_delta_pct=sl_proximity_delta_pct,
                tp_proximity_delta_pct=tp_proximity_delta_pct,
                median_timing_delta_seconds=median_timing_delta_seconds,
                bps=None,
                passed=False,
                unmeasured=tuple(unmeasured),
            )

        assert directional_concordance is not None
        assert spatial_iou is not None
        assert abstention_accuracy is not None
        assert median_timing_delta_seconds is not None

        s_action = 0.5 * directional_concordance + 0.5 * setup_recall
        s_spatial = spatial_iou
        s_abstain = abstention_accuracy
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
            unmeasured=(),
        )
