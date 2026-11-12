"""Project Proteus Constitutional Identity Guard & Bounded Self-Correction Engine (`proteus.constitution`).

Guarantees that as Project Proteus self-corrects and fine-tunes its parameters over time,
it can NEVER drift from `@learnernoearner`'s core cognitive identity or mutate into a
generic indicator bot.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from proteus.paths import state_path

FORBIDDEN_INDICATOR_PATTERNS: tuple[str, ...] = (
    r"(?:^|[\W_])rsi(?:$|[\W_0-9])",
    r"(?:^|[\W_])macd(?:$|[\W_0-9])",
    r"(?:^|[\W_])bollinger(?:$|[\W_0-9])",
    r"(?:^|[\W_])stochastic(?:$|[\W_0-9])",
    r"(?:^|[\W_])ichimoku(?:$|[\W_0-9])",
    r"(?:^|[\W_])adx_indicator(?:$|[\W_0-9])",
    r"(?:^|[\W_])ema_crossover(?:$|[\W_0-9])",
    r"(?:^|[\W_])sma_crossover(?:$|[\W_0-9])",
)

DEFAULT_CHECKPOINT_PATH = (
    Path(__file__).resolve().parents[3]
    / "benchmarks"
    / "constitutional_checkpoint.json"
)


class IdentityDriftError(RuntimeError):
    """Raised when a code change or parameter update violates Project Proteus's identity."""


@dataclass(frozen=True)
class ConstitutionalParameters:
    """Tunable cognitive parameters strictly bounded by Constitutional Corridors."""

    long_conviction_threshold: float = 0.65
    short_conviction_threshold: float = 0.85
    no_mans_land_abstain_prob: float = 0.92
    median_sl_long_pct: float = 0.0267
    median_sl_short_pct: float = 0.0217
    median_rr_long: float = 4.87
    median_rr_short: float = 4.46
    breakeven_trigger_r: float = 1.00
    level_proximity_pct: float = 0.0120
    wick_rejection_threshold: float = 0.3500
    max_open_positions: int = 3
    bedtime_start_hour_utc: int = 21
    generation: int = 1
    updated_at_utc: str = "2026-11-09T06:35:00+00:00"
    invalidated_generations: int = 0
    invalidated_at_utc: str = ""
    invalidated_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# Hard Constitutional Corridors: (min_allowed, anchor_prior, max_allowed)
CONSTITUTIONAL_CORRIDORS: dict[str, tuple[float, float, float]] = {
    "long_conviction_threshold": (0.60, 0.65, 0.75),
    "short_conviction_threshold": (0.80, 0.85, 0.93),
    "no_mans_land_abstain_prob": (0.85, 0.92, 0.98),
    "median_sl_long_pct": (0.0180, 0.0267, 0.0360),
    "median_sl_short_pct": (0.0140, 0.0217, 0.0300),
    "median_rr_long": (3.50, 4.87, 6.50),
    "median_rr_short": (3.20, 4.46, 5.80),
    "breakeven_trigger_r": (0.85, 1.00, 1.25),
    "level_proximity_pct": (0.0060, 0.0120, 0.0200),
    "wick_rejection_threshold": (0.25, 0.35, 0.50),
}


class ConstitutionalIdentityGuard:
    """Enforces immutable project identity invariants across parameters and source code."""

    @classmethod
    def validate_parameters(cls, params: ConstitutionalParameters) -> None:
        # 1. Verify every tunable parameter lies inside its Constitutional Corridor
        for field_name, (low, _anchor, high) in CONSTITUTIONAL_CORRIDORS.items():
            val = float(getattr(params, field_name))
            if not (low <= val <= high):
                raise IdentityDriftError(
                    f"Constitutional violation on '{field_name}': {val} outside allowed corridor [{low}, {high}]"
                )

        # 2. Enforce 80/20 Directional Conviction Gap (Short must require >= +0.15 higher conviction)
        conviction_gap = round(
            params.short_conviction_threshold - params.long_conviction_threshold, 4
        )
        if conviction_gap < 0.15:
            raise IdentityDriftError(
                f"Directional asymmetry violation: short_conviction_threshold ({params.short_conviction_threshold}) "
                f"must exceed long_conviction_threshold ({params.long_conviction_threshold}) by >= 0.15"
            )

        # 3. Enforce Directional Stop-Loss Asymmetry (Short wick SL must be tighter than Long swing SL)
        if params.median_sl_short_pct >= params.median_sl_long_pct:
            raise IdentityDriftError(
                f"Stop-loss asymmetry violation: median_sl_short_pct ({params.median_sl_short_pct}) "
                f"must remain tighter than median_sl_long_pct ({params.median_sl_long_pct})"
            )

        # 4. Enforce Directional R:R Asymmetry (Long expansion target >= Short rejection target)
        if params.median_rr_long < params.median_rr_short:
            raise IdentityDriftError(
                f"Target R:R asymmetry violation: median_rr_long ({params.median_rr_long}) "
                f"must be >= median_rr_short ({params.median_rr_short})"
            )

        # 5. Enforce Portfolio Slot Cap & Bedtime Window
        if not (1 <= params.max_open_positions <= 5):
            raise IdentityDriftError(
                f"Margin velocity slot cap violation: max_open_positions={params.max_open_positions} outside [1, 5]"
            )
        if not (20 <= params.bedtime_start_hour_utc <= 23):
            raise IdentityDriftError(
                f"Circadian derisking window violation: bedtime_start_hour_utc={params.bedtime_start_hour_utc}"
            )

    @classmethod
    def verify_codebase_purity(cls, src_root: Path | None = None) -> tuple[bool, int]:
        """Scan `src/proteus/` to guarantee zero lagging retail TA indicators enter the codebase."""
        root = src_root or (Path(__file__).resolve().parents[1])
        compiled = [re.compile(pat, re.IGNORECASE) for pat in FORBIDDEN_INDICATOR_PATTERNS]
        scanned_files = 0

        for py_file in sorted(root.rglob("*.py")):
            if py_file.resolve() == Path(__file__).resolve():
                continue
            scanned_files += 1
            text = py_file.read_text(encoding="utf-8")
            for regex in compiled:
                match = regex.search(text)
                if match:
                    raise IdentityDriftError(
                        f"Forbidden lagging retail indicator '{match.group(0)}' detected in {py_file.name}. "
                        "Project Proteus is a 3-tier structural range & visual saliency clone, never an indicator bot."
                    )
        return True, scanned_files


@dataclass(frozen=True)
class SelfCorrectionOutcome:
    accepted: bool
    generation: int
    previous_params: ConstitutionalParameters
    active_params: ConstitutionalParameters
    verified_bps: float
    reason: str


class BoundedSelfCorrector:
    """Fine-tunes cognitive parameters via prior-anchored Bayesian shrinkage with automatic rollback."""

    MIN_LEARNING_RATE: float = 0.05
    MAX_LEARNING_RATE: float = 0.25
    MIN_REQUIRED_BPS: float = 0.85

    def __init__(self, checkpoint_path: Path | None = None) -> None:
        self.checkpoint_path = checkpoint_path or state_path("constitutional_checkpoint.json")

    def load_active_parameters(self, *, seed: bool = True) -> ConstitutionalParameters:
        if self.checkpoint_path.exists():
            raw = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            params = ConstitutionalParameters(**raw)
            ConstitutionalIdentityGuard.validate_parameters(params)
            return params
        default_params = ConstitutionalParameters()
        ConstitutionalIdentityGuard.validate_parameters(default_params)
        if seed:
            self.save_checkpoint(default_params)
        return default_params

    def save_checkpoint(self, params: ConstitutionalParameters) -> None:
        ConstitutionalIdentityGuard.validate_parameters(params)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(
            json.dumps(params.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    def propose_fine_tune(
        self,
        observed_estimates: Mapping[str, float],
        learning_rate: float = 0.15,
        candidate_bps: float = 0.0,
        strict_mode: bool = False,
    ) -> SelfCorrectionOutcome:
        """Apply prior-anchored shrinkage and validate against Constitutional Corridors & BPS gate.

        Formula:
            theta_next = clip((1 - alpha) * theta_anchor + alpha * theta_observed, min, max)
        If `strict_mode=True`, out-of-corridor raw proposals raise `IdentityDriftError` directly;
        otherwise they are shrunk toward the Constitutional Anchor and clipped to the corridor,
        rolling back automatically if `candidate_bps < 0.85` or cross-parameter invariants fail.
        """
        current = self.load_active_parameters()
        alpha = max(self.MIN_LEARNING_RATE, min(self.MAX_LEARNING_RATE, learning_rate))

        if candidate_bps < self.MIN_REQUIRED_BPS:
            return SelfCorrectionOutcome(
                accepted=False,
                generation=current.generation,
                previous_params=current,
                active_params=current,
                verified_bps=candidate_bps,
                reason=(
                    f"Automatic Turing rollback: candidate BPS ({candidate_bps:.4f}) "
                    f"dropped below constitutional floor ({self.MIN_REQUIRED_BPS:.2f})."
                ),
            )

        updates: dict[str, object] = {}
        for key, observed_val in observed_estimates.items():
            if key not in CONSTITUTIONAL_CORRIDORS:
                raise IdentityDriftError(f"Unknown or non-tunable parameter: '{key}'")
            low, anchor, high = CONSTITUTIONAL_CORRIDORS[key]
            if strict_mode and not (low <= float(observed_val) <= high):
                raise IdentityDriftError(
                    f"Proposed value {observed_val} for '{key}' violates corridor [{low}, {high}]"
                )
            blended = (1.0 - alpha) * anchor + alpha * float(observed_val)
            clamped = round(max(low, min(high, blended)), 6)
            updates[key] = clamped

        updates["generation"] = current.generation + 1
        updates["updated_at_utc"] = datetime.now(UTC).isoformat()

        candidate = replace(current, **updates)
        try:
            ConstitutionalIdentityGuard.validate_parameters(candidate)
        except IdentityDriftError as exc:
            if strict_mode:
                raise
            return SelfCorrectionOutcome(
                accepted=False,
                generation=current.generation,
                previous_params=current,
                active_params=current,
                verified_bps=candidate_bps,
                reason=f"Automatic Constitutional rollback: {exc}",
            )

        self.save_checkpoint(candidate)
        return SelfCorrectionOutcome(
            accepted=True,
            generation=candidate.generation,
            previous_params=current,
            active_params=candidate,
            verified_bps=candidate_bps,
            reason=f"Accepted bounded fine-tune (alpha={alpha:.2f}, BPS={candidate_bps:.4f}).",
        )
