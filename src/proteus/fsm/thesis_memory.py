"""Stateful Multi-Attempt Thesis Memory FSM (`proteus.fsm.thesis_memory`).

Models `@learnernoearner`'s verbatim re-engagement cognition after a tight stop-out:
- Message #16395 ($SNDK): "Stoploss might be too tight but will be looking for another long if hits."
- Message #16412 ($WLD): "The trade hit our invalidation... if we fail to hold 0.417 then I will be looking for long below at around 0.387."

When a primary entry stops out on a wick sweep (`CLOSED_SL`) while the higher-timeframe
macro regime remains intact, `ThesisMemoryTracker` transitions the symbol into
`WATCHING_LOWER_DEMAND_REENTRY` anchored at `lower_demand_reentry_level`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ThesisMemoryEntry:
    symbol: str
    direction: str
    stopped_out_entry: float
    stopped_out_sl: float
    lower_demand_reentry_level: float
    attempts_used: int
    max_attempts: int
    state: str  # "WATCHING_LOWER_DEMAND_REENTRY", "REENTERED", "THESIS_EXPIRED"
    created_at_utc: str
    expires_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ThesisMemoryTracker:
    """Tracks invalidated primary setups to arm lower-tier structural re-entries."""

    MAX_REENTRY_ATTEMPTS: int = 2
    MEMORY_TTL_HOURS: int = 36
    REENTRY_TOUCH_TOLERANCE_PCT: float = 0.010

    def __init__(self) -> None:
        self._memories: dict[str, ThesisMemoryEntry] = {}

    def record_stop_out(
        self,
        symbol: str,
        direction: str,
        stopped_entry: float,
        stopped_sl: float,
        lower_demand_level: float,
        timestamp_utc: datetime,
    ) -> ThesisMemoryEntry:
        sym = symbol.upper().replace("USDT", "")
        prev = self._memories.get(sym)
        attempts = (prev.attempts_used + 1) if prev else 1
        expires = timestamp_utc + timedelta(hours=self.MEMORY_TTL_HOURS)
        state = (
            "WATCHING_LOWER_DEMAND_REENTRY"
            if attempts < self.MAX_REENTRY_ATTEMPTS
            else "THESIS_EXPIRED"
        )
        entry = ThesisMemoryEntry(
            symbol=sym,
            direction=direction,
            stopped_out_entry=stopped_entry,
            stopped_out_sl=stopped_sl,
            lower_demand_reentry_level=lower_demand_level,
            attempts_used=attempts,
            max_attempts=self.MAX_REENTRY_ATTEMPTS,
            state=state,
            created_at_utc=timestamp_utc.isoformat(),
            expires_at_utc=expires.isoformat(),
        )
        self._memories[sym] = entry
        return entry

    def evaluate_reentry_opportunity(
        self,
        symbol: str,
        current_price: float,
        now_utc: datetime,
        macro_breakdown: bool = False,
    ) -> tuple[bool, float, str]:
        """Return (should_reenter, conviction_boost, rationale)."""
        sym = symbol.upper().replace("USDT", "")
        mem = self._memories.get(sym)
        if not mem or mem.state != "WATCHING_LOWER_DEMAND_REENTRY":
            return False, 0.0, "No active lower-demand thesis memory."

        if macro_breakdown and mem.direction == "LONG":
            return False, 0.0, "Macro breakdown invalidated lower-demand Long thesis."

        exp_dt = datetime.fromisoformat(mem.expires_at_utc)
        if now_utc > exp_dt:
            return False, 0.0, "Thesis memory TTL expired."

        target = mem.lower_demand_reentry_level
        dist_pct = abs(current_price - target) / max(1e-12, target)
        if dist_pct <= self.REENTRY_TOUCH_TOLERANCE_PCT:
            return (
                True,
                0.10,
                f"Secondary lower-demand re-entry triggered at {target} "
                + f"(attempt {mem.attempts_used + 1}/{mem.max_attempts} after {mem.stopped_out_entry} stop-out).",
            )

        return False, 0.0, f"Waiting for lower demand level {target} (current dist {dist_pct*100:.2f}%)."
