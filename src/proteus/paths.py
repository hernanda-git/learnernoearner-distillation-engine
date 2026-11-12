"""Runtime state path resolution (`proteus.paths`).

The immutable corpus and documentation live under ``benchmarks/``. Mutable
runtime artifacts (paper ledger, watchdog state, self-improvement journal,
constitutional checkpoint, detection log) must not dirty the git working tree
on a production host. ``PROTEUS_STATE_DIR`` relocates them; the first access
seeds the new directory from the checked-in snapshot when one exists.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIR = REPO_ROOT / "benchmarks"


def state_dir() -> Path:
    """Return the mutable-state directory (``PROTEUS_STATE_DIR`` or benchmarks/)."""
    raw = os.getenv("PROTEUS_STATE_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_STATE_DIR


def state_path(name: str, *, seed: bool = True) -> Path:
    """Resolve ``name`` inside the state directory, seeding the first copy."""
    target = state_dir() / name
    if target.exists() or not seed or target.parent == DEFAULT_STATE_DIR:
        return target
    source = DEFAULT_STATE_DIR / name
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return target
