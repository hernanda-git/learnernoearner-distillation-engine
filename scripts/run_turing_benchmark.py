#!/usr/bin/env python3
"""Run the Project Proteus Cognitive Turing Benchmark on the 97-signal / 784-message corpus."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.replay import EmpiricalCorpusReplay  # noqa: E402


def main() -> int:
    replay = EmpiricalCorpusReplay()
    report = replay.run()
    print(json.dumps(dataclasses.asdict(report), indent=2))
    return 0 if report.parity_metrics.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
