#!/usr/bin/env python3
"""Step the Virtual Paper Exchange against the latest live Bitget shadow snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.paper import VirtualPaperExchange  # noqa: E402
from proteus.shadow import AssetShadowState, ForwardShadowScanner, LiveShadowSnapshot  # noqa: E402


def main() -> int:
    snapshot_path = REPO_ROOT / "benchmarks" / "live_shadow_snapshot.json"
    if snapshot_path.exists():
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
        states = [AssetShadowState(**s) for s in raw["states"]]
        snapshot = LiveShadowSnapshot(
            scanned_at_utc=raw["scanned_at_utc"],
            btc_1d_close=raw["btc_1d_close"],
            eth_1d_close=raw["eth_1d_close"],
            macro_regime=raw["macro_regime"],
            universe_evaluated=raw["universe_evaluated"],
            active_entries=raw["active_entries"],
            abstentions=raw["abstentions"],
            states=states,
        )
    else:
        snapshot = ForwardShadowScanner().scan_live_universe()

    exchange = VirtualPaperExchange()
    ledger = exchange.process_shadow_snapshot(snapshot)
    print(json.dumps(ledger.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
