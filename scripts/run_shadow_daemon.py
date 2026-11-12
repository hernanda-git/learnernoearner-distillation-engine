#!/usr/bin/env python3
"""Execute a live Phase 5 Forward Shadow scan against Bitget public market data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.paths import state_path
from proteus.shadow import ForwardShadowScanner


def main() -> int:
    scanner = ForwardShadowScanner()
    snapshot = scanner.scan_live_universe()
    out_path = state_path("live_shadow_snapshot.json", seed=False)
    out_path.write_text(json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
