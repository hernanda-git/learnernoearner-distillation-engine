"""AI-Agent Closed-Loop Self-Improvement Engine (`proteus.evolver`).

Combines the multi-agent verification architecture from `math-learn`
(`TelemetryScout` -> `AdversarialCritic` -> `TuringVerifier` -> `HashChainJournal`),
the fail-closed `CodexRunner` subprocess boundary from `fatty-multi-exchange-trader`
(`LAYER-1-CODEX.md`), and the `FAJ1` SHA-256 hash-chain audit journal from `fomoalpha`.

Deterministic Authority Rule (`fomoalpha/AGENTS.md`):
The AI agent proposes and critiques parameter hypotheses based on empirical MFE/MAE
and paper-ledger telemetry, while the deterministic `ConstitutionalIdentityGuard`,
`BoundedSelfCorrector`, and `BehavioralParityBenchmark` retain sole authority over
parameter admission and automatic rollback.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from proteus.backtest import LifecycleBacktestSimulator
from proteus.constitution import (
    CONSTITUTIONAL_CORRIDORS,
    BoundedSelfCorrector,
    ConstitutionalIdentityGuard,
)
from proteus.monitor import SelfMonitoringWatchdog
from proteus.replay import EmpiricalCorpusReplay

DEFAULT_JOURNAL_PATH = (
    Path(__file__).resolve().parents[3]
    / "benchmarks"
    / "self_improvement_journal.json"
)
DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "corpus"

_SECRET_REDACT_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{12,}|Bearer\s+[A-Za-z0-9_\-\.]+|BITGET_[A-Z_]+=\S+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CodexRunResult:
    invoked: bool
    terminal_failure: bool
    exit_code: int
    redacted_output: str


class FailClosedCodexBridge:
    """Fail-closed `codex exec` subprocess runner modeled on `LAYER-1-CODEX.md`."""

    def __init__(
        self,
        executable: str = "codex",
        timeout_seconds: int = 10,
        enabled: bool = False,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled

    @staticmethod
    def redact_secrets(text: str, max_bytes: int = 2048) -> str:
        cleaned = _SECRET_REDACT_RE.sub("[REDACTED_SECRET]", text or "")
        if len(cleaned) > max_bytes:
            return cleaned[:max_bytes] + "...[truncated]"
        return cleaned

    def try_advise(self, prompt: str) -> CodexRunResult:
        """Invoke `["codex", "exec", prompt]` with `shell=False` when enabled; fail closed otherwise."""
        if not self.enabled:
            return CodexRunResult(
                invoked=False,
                terminal_failure=False,
                exit_code=0,
                redacted_output="Built-in deterministic multi-agent critic active (external codex exec opt-in).",
            )
        bin_path = shutil.which(self.executable)
        if not bin_path:
            return CodexRunResult(
                invoked=False,
                terminal_failure=True,
                exit_code=127,
                redacted_output="codex CLI not installed on host; using built-in deterministic multi-agent critic.",
            )
        try:
            proc = subprocess.run(
                [bin_path, "exec", prompt],
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
            out = self.redact_secrets(proc.stdout or proc.stderr)
            return CodexRunResult(
                invoked=True,
                terminal_failure=(proc.returncode != 0),
                exit_code=proc.returncode,
                redacted_output=out,
            )
        except Exception as exc:
            return CodexRunResult(
                invoked=True,
                terminal_failure=True,
                exit_code=-1,
                redacted_output=self.redact_secrets(f"Codex invocation failed closed: {exc}"),
            )


@dataclass(frozen=True)
class AgenticStageTrace:
    agent_role: str  # "TelemetryScout", "AdversarialCritic", "TuringVerifier", "HashChainCommitter"
    verdict: str  # "PROPOSED", "APPROVED", "CHALLENGED", "COMMITTED", "ROLLED_BACK"
    summary: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class SelfImprovementJournalEntry:
    sequence_id: int
    timestamp_utc: str
    prev_hash: str
    entry_hash: str
    trigger_source: str
    monitor_status: str
    proposals: dict[str, float]
    learning_rate: float
    accepted: bool
    generation_before: int
    generation_after: int
    verified_bps: float
    verified_profit_factor: float
    verified_max_drawdown_r: float
    agent_traces: list[AgenticStageTrace]
    decision_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgenticSelfImprover:
    """4-Stage AI-Agent Self-Improving Pipeline with FAJ1 SHA-256 Hash-Chain Journal."""

    def __init__(
        self,
        journal_path: Path | None = None,
        corpus_dir: Path | None = None,
        corrector: BoundedSelfCorrector | None = None,
        watchdog: SelfMonitoringWatchdog | None = None,
    ) -> None:
        self.journal_path = journal_path or DEFAULT_JOURNAL_PATH
        self.corpus_dir = corpus_dir or DEFAULT_CORPUS_DIR
        self.corrector = corrector or BoundedSelfCorrector()
        self.watchdog = watchdog or SelfMonitoringWatchdog()
        self.codex_bridge = FailClosedCodexBridge()

    @staticmethod
    def _compute_entry_hash(prev_hash: str, payload_without_hash: dict[str, Any]) -> str:
        canonical = json.dumps(payload_without_hash, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256()
        digest.update(prev_hash.encode("utf-8"))
        digest.update(b":")
        digest.update(canonical)
        return digest.hexdigest()

    def load_journal(self) -> list[dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        rows: list[dict[str, Any]] = json.loads(self.journal_path.read_text(encoding="utf-8"))
        return rows

    def verify_journal_hash_chain(self) -> tuple[bool, int]:
        """Verify cryptographic integrity of the FAJ1 hash-chain journal."""
        rows = self.load_journal()
        prev = "0" * 64
        for idx, row in enumerate(rows):
            if row.get("prev_hash") != prev:
                return False, idx
            check_copy = {k: v for k, v in row.items() if k != "entry_hash"}
            expected = self._compute_entry_hash(prev, check_copy)
            if row.get("entry_hash") != expected:
                return False, idx
            prev = expected
        return True, len(rows)

    def run_improvement_cycle(
        self,
        trigger_source: str = "autonomous_daemon_cycle",
        custom_proposals: dict[str, float] | None = None,
        learning_rate: float = 0.12,
    ) -> SelfImprovementJournalEntry:
        now_str = datetime.now(timezone.utc).isoformat()
        traces: list[AgenticStageTrace] = []

        # Step 0: Self-Monitoring Watchdog Gate
        mon = self.watchdog.evaluate_and_heal()
        current_params = self.corrector.load_active_parameters()

        # Stage 1: TelemetryScoutAgent — mine empirical MFE/MAE & whipsaw telemetry
        traj_path = self.corpus_dir / "signal_candle_trajectories.json"
        trajectories: list[dict[str, Any]] = (
            json.loads(traj_path.read_text(encoding="utf-8")) if traj_path.exists() else []
        )
        resolved = [t for t in trajectories if t.get("post_48h_bars", 0) > 0]
        whipsaws = [
            t
            for t in resolved
            if t.get("first_hit_1r_min") is not None
            and t.get("first_hit_sl_min") is not None
            and t["first_hit_1r_min"] < t["first_hit_sl_min"]
        ]
        whipsaw_rate = round(len(whipsaws) / max(1, len(resolved)), 4)

        if custom_proposals is not None:
            proposals = dict(custom_proposals)
        else:
            # Data-driven empirical proposal derived from 87-signal MFE/MAE & 97-signal quantiles:
            # Slightly tighten breakeven_trigger_r (0.98R) when whipsaw rate > 30%,
            # and refine Long/Short SL & R:R toward observed medians.
            proposals = {
                "breakeven_trigger_r": 0.98 if whipsaw_rate >= 0.30 else 1.00,
                "median_sl_long_pct": 0.0266,
                "median_sl_short_pct": 0.0216,
                "median_rr_long": 4.88,
                "median_rr_short": 4.46,
            }

        codex_note = self.codex_bridge.try_advise(
            f"Analyze Proteus telemetry: whipsaw_rate={whipsaw_rate}, proposals={proposals}"
        )

        traces.append(
            AgenticStageTrace(
                agent_role="TelemetryScoutAgent",
                verdict="PROPOSED",
                summary=(
                    f"Analyzed {len(resolved)} Bitget 1H candle trajectories "
                    f"(whipsaw rate {whipsaw_rate*100:.1f}%) and proposed {len(proposals)} parameter refinements."
                ),
                evidence={
                    "resolved_trajectories": len(resolved),
                    "whipsaw_reversals": len(whipsaws),
                    "proposed_estimates": proposals,
                    "codex_cli_bridge": codex_note.redacted_output,
                },
            )
        )

        # Stage 2: AdversarialCriticAgent — challenge proposal against IDENTITY.md & corridors
        critic_issues: list[str] = []
        if mon.latch_active:
            critic_issues.append(f"Self-monitor latch is active: {mon.latch_reason}")

        for k, v in proposals.items():
            if k not in CONSTITUTIONAL_CORRIDORS:
                critic_issues.append(f"Parameter '{k}' is not in CONSTITUTIONAL_CORRIDORS")
            else:
                low, anchor, high = CONSTITUTIONAL_CORRIDORS[k]
                if not (low <= float(v) <= high):
                    critic_issues.append(
                        f"Raw proposal {k}={v} exceeds corridor [{low}, {high}] (anchor={anchor})"
                    )

        pure_code, scanned_files = ConstitutionalIdentityGuard.verify_codebase_purity()
        if not pure_code:
            critic_issues.append("Codebase purity check failed")

        critic_verdict = "CHALLENGED" if critic_issues else "APPROVED"
        traces.append(
            AgenticStageTrace(
                agent_role="AdversarialCriticAgent",
                verdict=critic_verdict,
                summary=(
                    "Verified zero lagging indicators across all source files and checked corridor bounds."
                    if not critic_issues
                    else f"Raised {len(critic_issues)} constitutional challenge(s): {critic_issues}"
                ),
                evidence={
                    "codebase_files_verified": scanned_files,
                    "challenges": critic_issues,
                },
            )
        )

        # Stage 3: TuringVerifierAgent — run replay & comparative backtest gates
        replay = EmpiricalCorpusReplay().run()
        bt = LifecycleBacktestSimulator().run_comparative_backtest()
        bps = replay.parity_metrics.bps
        pf = bt.proteus_distilled_fsm.profit_factor
        max_dd = bt.proteus_distilled_fsm.max_drawdown_r

        if critic_issues:
            outcome_accepted = False
            gen_after = current_params.generation
            reason = f"Rejected by AdversarialCriticAgent: {'; '.join(critic_issues)}"
        else:
            sc_outcome = self.corrector.propose_fine_tune(
                observed_estimates=proposals,
                learning_rate=learning_rate,
                candidate_bps=bps if bps is not None else 0.0,
                strict_mode=False,
            )
            outcome_accepted = sc_outcome.accepted
            gen_after = sc_outcome.generation
            reason = sc_outcome.reason

        traces.append(
            AgenticStageTrace(
                agent_role="TuringVerifierAgent",
                verdict="APPROVED" if outcome_accepted else "ROLLED_BACK",
                summary=(
                    f"Turing gates: BPS={'UNMEASURED' if bps is None else f'{bps:.4f}'}, "
                    f"ProfitFactor={pf:.2f}, MaxDD={max_dd:.2f}R. "
                    f"{'Parameter update accepted.' if outcome_accepted else 'Parameter update rejected.'}"
                ),
                evidence={
                    "bps": bps,
                    "bps_measured": bps is not None,
                    "profit_factor": pf,
                    "max_drawdown_r": max_dd,
                    "accepted": outcome_accepted,
                },
            )
        )

        # Stage 4: HashChainCommitter — append immutable FAJ1 SHA-256 hash-chain record
        existing_rows = self.load_journal()
        seq_id = len(existing_rows) + 1
        prev_hash = existing_rows[-1]["entry_hash"] if existing_rows else ("0" * 64)

        traces.append(
            AgenticStageTrace(
                agent_role="HashChainCommitter",
                verdict="COMMITTED" if outcome_accepted else "ROLLED_BACK",
                summary=f"Appended hash-chained journal entry #{seq_id} (Gen {current_params.generation} -> Gen {gen_after}).",
                evidence={"sequence_id": seq_id, "prev_hash_prefix": prev_hash[:16]},
            )
        )

        draft_dict: dict[str, Any] = {
            "sequence_id": seq_id,
            "timestamp_utc": now_str,
            "prev_hash": prev_hash,
            "trigger_source": trigger_source,
            "monitor_status": mon.overall_status,
            "proposals": proposals,
            "learning_rate": learning_rate,
            "accepted": outcome_accepted,
            "generation_before": current_params.generation,
            "generation_after": gen_after,
            "verified_bps": bps if bps is not None else 0.0,
            "verified_profit_factor": pf,
            "verified_max_drawdown_r": max_dd,
            "agent_traces": [asdict(t) for t in traces],
            "decision_reason": reason,
        }
        entry_hash = self._compute_entry_hash(prev_hash, draft_dict)

        entry = SelfImprovementJournalEntry(
            sequence_id=seq_id,
            timestamp_utc=now_str,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            trigger_source=trigger_source,
            monitor_status=mon.overall_status,
            proposals=proposals,
            learning_rate=learning_rate,
            accepted=outcome_accepted,
            generation_before=current_params.generation,
            generation_after=gen_after,
            verified_bps=bps if bps is not None else 0.0,
            verified_profit_factor=pf,
            verified_max_drawdown_r=max_dd,
            agent_traces=traces,
            decision_reason=reason,
        )

        existing_rows.append(entry.to_dict())
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path.write_text(
            json.dumps(existing_rows, indent=2) + "\n", encoding="utf-8"
        )
        return entry
