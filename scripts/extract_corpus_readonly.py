#!/usr/bin/env python3
"""Read-only corpus snapshot extractor for Project Proteus.

Exports `telegram_messages` and `canonical_signals` from a local SQLite/JSON
snapshot into an air-gapped JSONL corpus with SHA-256 manifest verification.
Strictly refuses execution if any live exchange credentials exist in `os.environ`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Allow running directly from repository root without editable install
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.engine import ProteusDistillationEngine  # noqa: E402


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_sqlite_readonly(db_path: Path, output_dir: Path) -> dict[str, Any]:
    """Open SQLite source in immutable read-only URI mode and export tables."""
    ProteusDistillationEngine.verify_air_gap(os.environ)

    if not db_path.exists():
        raise FileNotFoundError(f"Source snapshot not found: {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    uri = f"{db_path.resolve().as_uri()}?mode=ro"

    manifest: dict[str, Any] = {"source": str(db_path), "tables": {}}
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        tables = [
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('telegram_messages', 'canonical_signals')"
            ).fetchall()
        ]
        for table in tables:
            out_file = output_dir / f"{table}.jsonl"
            rows = cursor.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
            with out_file.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(dict(row), sort_keys=True) + "\n")
            manifest["tables"][table] = {
                "rows": len(rows),
                "sha256": compute_sha256(out_file),
            }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Air-gapped read-only corpus snapshot extractor for Project Proteus."
    )
    parser.add_argument(
        "--source-sqlite",
        type=Path,
        required=True,
        help="Path to read-only SQLite snapshot containing telegram_messages and canonical_signals.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "corpus",
        help="Destination directory for exported JSONL artifacts.",
    )
    args = parser.parse_args(argv)
    manifest = extract_sqlite_readonly(args.source_sqlite, args.output_dir)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
