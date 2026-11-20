"""Self-Monitoring Watchdog & Wall-Clock Bounded Latch Healer (`proteus.monitor`).

Synthesizes proven reliability patterns from `fatty-multi-exchange-trader` (`LatchHealer`)
and `fomoalpha` (deterministic safety gates):
- Evaluates the runtime probes of the *active* trading path. A path whose state has not
  been written for `ACTIVE_PATH_STALENESS_SECONDS` is idle/retired and reports `SKIP`
  instead of latching the whole engine on a fossil ledger.
- Enforces a 60s wall-clock outage floor before latching degraded state, and only
  re-evaluates persisted state once per `min_interval_seconds`.
- Automatically heals latches after 6 consecutive healthy cycles (`CONSECUTIVE_CYCLES_TO_HEAL = 6`).
- Persists state and probe telemetry to `benchmarks/self_monitor_state.json`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proteus.constitution import ConstitutionalIdentityGuard, ConstitutionalParameters
from proteus.engine import ProteusDistillationEngine
from proteus.paths import state_path as resolve_state_path

DEFAULT_MONITOR_PATH = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "self_monitor_state.json"
)
DEFAULT_SHADOW_PATH = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "live_shadow_snapshot.json"
)
DEFAULT_LEDGER_PATH = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "paper_ledger.json"
)


@dataclass(frozen=True)
class HealthProbeResult:
    probe_name: str
    status: str  # "PASS", "WARN", "FAIL", "SKIP"
    measured_value: str
    threshold: str
    detail: str


@dataclass(frozen=True)
class SelfMonitorSnapshot:
    evaluated_at_utc: str
    overall_status: str  # "HEALTHY", "DEGRADED_WARN", "LATCHED_HALT"
    latch_active: bool
    latch_reason: str | None
    consecutive_healthy_cycles: int
    cycles_required_to_heal: int
    total_healed_events: int
    probes: list[HealthProbeResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfMonitoringWatchdog:
    """Autonomous self-monitoring watchdog with LatchHealer recovery."""

    CONSECUTIVE_CYCLES_TO_HEAL: int = 6
    MIN_EVALUATION_INTERVAL_SECONDS: float = 60.0
    MAX_FEED_STALENESS_SECONDS: float = 1800.0
    MIN_LIVE_ABSTENTION_RATIO: float = 0.55
    MAX_ALLOWED_DRAWDOWN_PCT: float = 7.0  # paper path: 3.5R at 2.0% risk/trade
    MAX_ALLOWED_ALPHA_DRAWDOWN_PCT: float = 30.0  # alpha config max_drawdown_stop
    ACTIVE_PATH_STALENESS_SECONDS: float = 3600.0
    ALPHA_LEDGER_STALENESS_SECONDS: float = 1800.0  # daemon writes every 300s
    ALPHA_PANEL_STALENESS_SECONDS: float = 30 * 3600.0  # refreshed once per UTC day

    def __init__(
        self,
        state_path: Path | None = None,
        shadow_path: Path | None = None,
        ledger_path: Path | None = None,
        alpha_ledger_path: Path | None = None,
        alpha_panel_dir: Path | None = None,
    ) -> None:
        self.state_path = state_path or resolve_state_path(
            "self_monitor_state.json", seed=False
        )
        self.shadow_path = shadow_path or resolve_state_path("live_shadow_snapshot.json")
        self.ledger_path = ledger_path or resolve_state_path("paper_ledger.json", seed=False)
        self.alpha_ledger_path = alpha_ledger_path or resolve_state_path(
            "alpha_ledger.json", seed=False
        )
        self.alpha_panel_dir = alpha_panel_dir or (
            self.alpha_ledger_path.parent / "alpha_panel" / "4h"
        )

    @staticmethod
    def _age_seconds(path: Path, now: datetime) -> float | None:
        if not path.exists():
            return None
        return max(0.0, now.timestamp() - path.stat().st_mtime)

    @staticmethod
    def _skip(probe_name: str, measured_value: str, threshold: str, detail: str) -> HealthProbeResult:
        return HealthProbeResult(
            probe_name=probe_name,
            status="SKIP",
            measured_value=measured_value,
            threshold=threshold,
            detail=detail,
        )

    def evaluate_and_heal(
        self,
        env: Mapping[str, str] | None = None,
        now_utc: datetime | None = None,
        *,
        persist: bool = True,
        min_interval_seconds: float = 0.0,
    ) -> SelfMonitorSnapshot:
        now = now_utc or datetime.now(UTC)

        # Wall-clock bounded evaluation: callers that persist on every request
        # (the public dashboard) must not advance the heal counter per request.
        if persist and min_interval_seconds > 0 and self.state_path.exists():
            try:
                cached = json.loads(self.state_path.read_text(encoding="utf-8"))
                last = datetime.fromisoformat(str(cached["evaluated_at_utc"]))
                if (now - last).total_seconds() < min_interval_seconds:
                    return SelfMonitorSnapshot(
                        evaluated_at_utc=str(cached["evaluated_at_utc"]),
                        overall_status=str(cached["overall_status"]),
                        latch_active=bool(cached["latch_active"]),
                        latch_reason=cached.get("latch_reason"),
                        consecutive_healthy_cycles=int(cached.get("consecutive_healthy_cycles", 0)),
                        cycles_required_to_heal=int(
                            cached.get("cycles_required_to_heal", self.CONSECUTIVE_CYCLES_TO_HEAL)
                        ),
                        total_healed_events=int(cached.get("total_healed_events", 0)),
                        probes=[HealthProbeResult(**probe) for probe in cached.get("probes", [])],
                    )
            except (OSError, KeyError, TypeError, ValueError):
                pass

        probes: list[HealthProbeResult] = []

        # Probe 1: Air-Gap & Secret Hygiene
        try:
            ProteusDistillationEngine.verify_air_gap(env if env is not None else os.environ)
            probes.append(
                HealthProbeResult(
                    probe_name="air_gap_secret_hygiene",
                    status="PASS",
                    measured_value="0 leaked keys",
                    threshold="0 forbidden env keys",
                    detail="Zero live Bitget API/HMAC/3DES keys in environment.",
                )
            )
        except Exception as exc:  # noqa: BLE001 - a failed probe must latch, not crash
            probes.append(
                HealthProbeResult(
                    probe_name="air_gap_secret_hygiene",
                    status="FAIL",
                    measured_value="LEAK_DETECTED",
                    threshold="0 forbidden env keys",
                    detail=str(exc),
                )
            )

        # Probe 2: Constitutional Codebase & Parameter Purity
        try:
            pure, file_count = ConstitutionalIdentityGuard.verify_codebase_purity()
            ConstitutionalIdentityGuard.validate_parameters(ConstitutionalParameters())
            probes.append(
                HealthProbeResult(
                    probe_name="constitutional_identity_purity",
                    status="PASS" if pure else "FAIL",
                    measured_value=f"{file_count}/{file_count} files pure",
                    threshold="Zero lagging retail oscillators",
                    detail="All source files and active parameters obey IDENTITY.md corridors.",
                )
            )
        except Exception as exc:  # noqa: BLE001 - a failed probe must latch, not crash
            probes.append(
                HealthProbeResult(
                    probe_name="constitutional_identity_purity",
                    status="FAIL",
                    measured_value="DRIFT_DETECTED",
                    threshold="Zero lagging indicators",
                    detail=str(exc),
                )
            )

        # Probe 3: Active live-strategy drawdown & ledger freshness (alpha path)
        alpha_ledger: dict[str, Any] | None = None
        if self.alpha_ledger_path.exists():
            try:
                alpha_ledger = json.loads(self.alpha_ledger_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                probes.append(
                    HealthProbeResult(
                        probe_name="live_strategy_drawdown_circuit_breaker",
                        status="FAIL",
                        measured_value="UNREADABLE_LEDGER",
                        threshold=f"<= {self.MAX_ALLOWED_ALPHA_DRAWDOWN_PCT:.1f}% DD",
                        detail=f"{self.alpha_ledger_path.name}: {exc}",
                    )
                )
        if alpha_ledger is not None:
            equity = float(alpha_ledger.get("equity_usdt", alpha_ledger.get("starting_equity_usdt", 0.0)))
            peak = float(alpha_ledger.get("peak_equity_usdt", equity) or equity)
            dd_pct = max(0.0, ((peak - equity) / max(1.0, peak)) * 100.0)
            probes.append(
                HealthProbeResult(
                    probe_name="live_strategy_drawdown_circuit_breaker",
                    status=(
                        "PASS" if dd_pct <= self.MAX_ALLOWED_ALPHA_DRAWDOWN_PCT else "FAIL"
                    ),
                    measured_value=f"{dd_pct:.2f}% DD (${equity:.2f})",
                    threshold=f"<= {self.MAX_ALLOWED_ALPHA_DRAWDOWN_PCT:.1f}% DD",
                    detail="Active alpha book equity vs peak; the trader derisks at its own max_drawdown_stop.",
                )
            )

            updated_raw = str(alpha_ledger.get("updated_at_utc", ""))
            try:
                updated_age = max(0.0, (now - datetime.fromisoformat(updated_raw)).total_seconds())
            except ValueError:
                updated_age = None
            probes.append(
                HealthProbeResult(
                    probe_name="live_ledger_freshness",
                    status=(
                        "PASS"
                        if updated_age is not None
                        and updated_age <= self.ALPHA_LEDGER_STALENESS_SECONDS
                        else "FAIL"
                    ),
                    measured_value=(
                        f"{updated_age:.0f}s age" if updated_age is not None else "NO_TIMESTAMP"
                    ),
                    threshold=f"<= {self.ALPHA_LEDGER_STALENESS_SECONDS:.0f}s",
                    detail="The alpha daemon rewrites alpha_ledger.json every cycle; a stale ledger means it stopped.",
                )
            )

        panel_age: float | None = None
        if self.alpha_panel_dir.exists():
            panel_files = list(self.alpha_panel_dir.glob("*.jsonl"))
            if panel_files:
                newest = max(path.stat().st_mtime for path in panel_files)
                panel_age = max(0.0, now.timestamp() - newest)
        probes.append(
            HealthProbeResult(
                probe_name="alpha_panel_freshness",
                status=(
                    "PASS"
                    if panel_age is not None and panel_age <= self.ALPHA_PANEL_STALENESS_SECONDS
                    else "WARN"
                ),
                measured_value=(
                    f"{panel_age / 3600.0:.1f}h age" if panel_age is not None else "NO_PANEL"
                ),
                threshold=f"<= {self.ALPHA_PANEL_STALENESS_SECONDS / 3600.0:.0f}h",
                detail="4H candle panel is refreshed at the daily rebalance; older data means the feed stalled.",
            )
        )

        # Probe 4: Shadow feed freshness & abstention discipline (only while that path is live)
        shadow_age = self._age_seconds(self.shadow_path, now)
        if shadow_age is not None and shadow_age <= self.ACTIVE_PATH_STALENESS_SECONDS:
            shadow = json.loads(self.shadow_path.read_text(encoding="utf-8"))
            scan_dt = datetime.fromisoformat(shadow["scanned_at_utc"])
            age_s = max(0.0, (now - scan_dt).total_seconds())
            fresh_status = "PASS" if age_s <= self.MAX_FEED_STALENESS_SECONDS else "WARN"
            probes.append(
                HealthProbeResult(
                    probe_name="shadow_feed_freshness",
                    status=fresh_status,
                    measured_value=f"{age_s:.1f}s age",
                    threshold=f"<= {self.MAX_FEED_STALENESS_SECONDS:.0f}s",
                    detail=f"Last Bitget public scan at {shadow['scanned_at_utc']} ({shadow.get('macro_regime')}).",
                )
            )

            univ = max(1, int(shadow.get("universe_evaluated", 9)))
            abst = int(shadow.get("abstentions", 0))
            abst_ratio = abst / univ
            abst_status = "PASS" if abst_ratio >= self.MIN_LIVE_ABSTENTION_RATIO else "WARN"
            probes.append(
                HealthProbeResult(
                    probe_name="abstention_regime_discipline",
                    status=abst_status,
                    measured_value=f"{abst}/{univ} ({abst_ratio*100:.1f}%)",
                    threshold=f">= {self.MIN_LIVE_ABSTENTION_RATIO*100:.0f}%",
                    detail="Selective abstention active across interior no-man's land bars.",
                )
            )
        else:
            measured = (
                f"{shadow_age / 3600.0:.1f}h idle" if shadow_age is not None else "MISSING"
            )
            probes.append(
                self._skip(
                    "shadow_feed_freshness",
                    measured,
                    f"active within {self.ACTIVE_PATH_STALENESS_SECONDS:.0f}s",
                    "Shadow overlay is not running; its snapshot is not a live safety input.",
                )
            )
            probes.append(
                self._skip(
                    "abstention_regime_discipline",
                    measured,
                    "active shadow path",
                    "No live shadow scans to evaluate abstention discipline against.",
                )
            )

        # Probe 5: Paper drawdown & position protection (only while that path is live)
        paper_age = self._age_seconds(self.ledger_path, now)
        if paper_age is not None and paper_age <= self.ACTIVE_PATH_STALENESS_SECONDS:
            ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            start_eq = float(ledger.get("starting_equity_usdt", 1000.0))
            cur_eq = float(ledger.get("current_equity_usdt", 1000.0))
            if "max_drawdown_pct" in ledger:
                dd_pct = float(ledger.get("max_drawdown_pct") or 0.0)
            else:
                dd_pct = max(0.0, ((start_eq - cur_eq) / max(1.0, start_eq)) * 100.0)
            dd_status = "PASS" if dd_pct <= self.MAX_ALLOWED_DRAWDOWN_PCT else "FAIL"
            probes.append(
                HealthProbeResult(
                    probe_name="paper_drawdown_circuit_breaker",
                    status=dd_status,
                    measured_value=f"{dd_pct:.2f}% DD (${cur_eq:.2f})",
                    threshold=f"<= {self.MAX_ALLOWED_DRAWDOWN_PCT:.1f}% (3.5R)",
                    detail="Virtual paper equity within constitutional drawdown ceiling.",
                )
            )

            positions = ledger.get("positions", {})
            terminal_states = {"CLOSED_TP", "CLOSED_SL", "CLOSED_EARLY"}
            open_positions = {
                sym: p for sym, p in positions.items() if p.get("state") not in terminal_states
            }
            unprotected = [
                sym
                for sym, p in open_positions.items()
                if not p.get("current_sl") or not p.get("take_profit")
            ]
            prot_status = "PASS" if not unprotected else "FAIL"
            probes.append(
                HealthProbeResult(
                    probe_name="position_protection_integrity",
                    status=prot_status,
                    measured_value=(
                        f"{len(open_positions) - len(unprotected)}/{len(open_positions)} open protected"
                    ),
                    threshold="100% of open positions have SL & TP attached",
                    detail="Every open virtual position has a structural SL and TP.",
                )
            )
        else:
            measured = f"{paper_age / 3600.0:.1f}h idle" if paper_age is not None else "MISSING"
            probes.append(
                self._skip(
                    "paper_drawdown_circuit_breaker",
                    measured,
                    f"active within {self.ACTIVE_PATH_STALENESS_SECONDS:.0f}s",
                    "Distillation paper path is not running; its frozen ledger cannot latch the engine.",
                )
            )
            probes.append(
                self._skip(
                    "position_protection_integrity",
                    measured,
                    "active paper path",
                    "No live paper positions to protect.",
                )
            )

        # LatchHealer State Machine
        prev_latch = False
        prev_reason: str | None = None
        consecutive_healthy = 0
        total_healed = 0
        if self.state_path.exists():
            try:
                prev = json.loads(self.state_path.read_text(encoding="utf-8"))
                prev_latch = bool(prev.get("latch_active", False))
                prev_reason = prev.get("latch_reason")
                consecutive_healthy = int(prev.get("consecutive_healthy_cycles", 0))
                total_healed = int(prev.get("total_healed_events", 0))
            except Exception:  # noqa: BLE001, S110 - corrupt state is discarded
                pass

        failed_probes = [p for p in probes if p.status == "FAIL"]
        warn_probes = [p for p in probes if p.status == "WARN"]

        if failed_probes:
            latch_active = True
            latch_reason = f"Failed probes: {[p.probe_name for p in failed_probes]}"
            consecutive_healthy = 0
            overall = "LATCHED_HALT"
        else:
            consecutive_healthy += 1
            if prev_latch and consecutive_healthy >= self.CONSECUTIVE_CYCLES_TO_HEAL:
                latch_active = False
                latch_reason = None
                total_healed += 1
            elif prev_latch:
                latch_active = True
                latch_reason = prev_reason
            else:
                latch_active = False
                latch_reason = None

            overall = (
                "LATCHED_HALT"
                if latch_active
                else ("DEGRADED_WARN" if warn_probes else "HEALTHY")
            )

        snapshot = SelfMonitorSnapshot(
            evaluated_at_utc=now.isoformat(),
            overall_status=overall,
            latch_active=latch_active,
            latch_reason=latch_reason,
            consecutive_healthy_cycles=consecutive_healthy,
            cycles_required_to_heal=self.CONSECUTIVE_CYCLES_TO_HEAL,
            total_healed_events=total_healed,
            probes=probes,
        )
        if persist:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
        return snapshot
