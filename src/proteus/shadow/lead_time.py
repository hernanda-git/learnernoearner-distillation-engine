"""Phase 6.1: Shadow lead-time comparator (`proteus.shadow.lead_time`).

Lead time is only reported when both timestamps exist:

- ``human_posted_at_utc`` from the Telegram corpus.
- ``proteus_detected_at_utc`` from an actual logged scan detection.

The corpus does not contain Proteus detection timestamps, so the default
result is ``UNMEASURED``. No synthetic lead-time formula is used.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from proteus.market import normalize_base_symbol

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "corpus"
DEFAULT_LEAD_LOG_PATH = (
    Path(__file__).resolve().parents[3] / "benchmarks" / "shadow_lead_time_log.json"
)


@dataclass(frozen=True)
class LeadTimeComparison:
    symbol: str
    direction: str
    proteus_detected_at_utc: str
    human_posted_at_utc: str
    delta_t_seconds: float
    proteus_entry: str
    human_entry: str
    entry_delta_pct: float
    front_ran_or_simultaneous: bool


@dataclass(frozen=True)
class ShadowLeadTimeSummary:
    evaluated_pairs: int
    median_delta_t_seconds: float | None
    mean_delta_t_seconds: float | None
    front_run_or_simultaneous_rate_pct: float
    comparisons: list[LeadTimeComparison]
    status: str = "UNMEASURED"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ShadowLeadTimeComparator:
    """Evaluates timing parity between logged Proteus detections and human posts."""

    def __init__(
        self,
        corpus_dir: Path | None = None,
        log_path: Path | None = None,
        ssh_relay_host: str | None = "valarion@46.202.155.192",
    ) -> None:
        self.corpus_dir = corpus_dir or DEFAULT_CORPUS_DIR
        self.log_path = log_path or DEFAULT_LEAD_LOG_PATH
        self.ssh_relay_host = ssh_relay_host

    def fetch_recent_human_signals(self, limit: int = 25) -> list[dict[str, Any]]:
        """Poll recent canonical signals from the local corpus snapshot."""
        signals_file = self.corpus_dir / "canonical_signals.json"
        if signals_file.exists():
            rows: list[dict[str, Any]] = json.loads(signals_file.read_text(encoding="utf-8"))
            return rows[-limit:]

        if not self.ssh_relay_host:
            return []

        sql = (
            "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json) FROM ("
            "SELECT cs.pair_token, cs.direction, cs.entry_price::text AS entry_price, "
            "tm.received_at FROM canonical_signals cs "
            "LEFT JOIN telegram_messages tm ON tm.id = cs.message_id "
            f"ORDER BY cs.created_at DESC LIMIT {int(limit)}) t;"
        )
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            self.ssh_relay_host,
            f'docker exec fatty-multi-exchange-trader-postgres-1 psql -U fatty_app -d fatty_trader -t -A -c "{sql}"',
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip().startswith("[")]
        return json.loads(lines[-1]) if lines else []

    def evaluate_shadow_lead_time(
        self,
        human_signals: Sequence[dict[str, Any]] | None = None,
    ) -> ShadowLeadTimeSummary:
        """Compute lead time from actual paired detections.

        A signal is only counted when it carries ``proteus_detected_at_utc``
        (or ``detected_at``) from a scan log. Without that timestamp the result
        is ``UNMEASURED`` — never a fabricated negative delta.
        """
        signals = (
            list(human_signals)
            if human_signals is not None
            else self.fetch_recent_human_signals(25)
        )
        comparisons: list[LeadTimeComparison] = []

        for sig in signals:
            detected = sig.get("proteus_detected_at_utc") or sig.get("detected_at")
            human_ts = sig.get("human_posted_at_utc") or sig.get("received_at") or sig.get("created_at")
            if not detected or not human_ts:
                continue
            try:
                proteus_dt = datetime.fromisoformat(str(detected))
                human_dt = datetime.fromisoformat(str(human_ts))
            except ValueError:
                continue

            delta_t = round((proteus_dt - human_dt).total_seconds(), 2)
            proteus_entry = str(sig.get("proteus_entry", sig.get("entry_price", "")))
            human_entry = str(sig.get("entry_price", ""))
            try:
                entry_delta_pct = round(
                    abs(float(proteus_entry) - float(human_entry))
                    / max(1e-12, float(human_entry))
                    * 100.0,
                    4,
                )
            except ValueError:
                entry_delta_pct = 0.0

            comparisons.append(
                LeadTimeComparison(
                    symbol=normalize_base_symbol(str(sig.get("pair_token") or sig.get("symbol") or "?")),
                    direction=sig["direction"],
                    proteus_detected_at_utc=proteus_dt.isoformat(),
                    human_posted_at_utc=human_dt.isoformat(),
                    delta_t_seconds=delta_t,
                    proteus_entry=proteus_entry,
                    human_entry=human_entry,
                    entry_delta_pct=entry_delta_pct,
                    front_ran_or_simultaneous=delta_t <= 0.0,
                )
            )

        if not comparisons:
            summary = ShadowLeadTimeSummary(
                evaluated_pairs=0,
                median_delta_t_seconds=None,
                mean_delta_t_seconds=None,
                front_run_or_simultaneous_rate_pct=0.0,
                comparisons=[],
                status="UNMEASURED",
            )
        else:
            deltas = sorted(c.delta_t_seconds for c in comparisons)
            n = len(deltas)
            median_dt = deltas[n // 2] if n % 2 else round((deltas[n // 2 - 1] + deltas[n // 2]) / 2.0, 2)
            summary = ShadowLeadTimeSummary(
                evaluated_pairs=n,
                median_delta_t_seconds=median_dt,
                mean_delta_t_seconds=round(sum(deltas) / n, 2),
                front_run_or_simultaneous_rate_pct=round(
                    sum(1 for c in comparisons if c.front_ran_or_simultaneous) / n * 100.0, 1
                ),
                comparisons=comparisons,
                status="MEASURED",
            )

        self.log_path.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
        return summary
