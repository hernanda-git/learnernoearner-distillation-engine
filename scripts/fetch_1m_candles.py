#!/usr/bin/env python3
"""Fetch 1-minute candles around every canonical signal (`scripts/fetch_1m_candles.py`).

The corpus currently ships 1H candles. The FSM cannot resolve intrabar order
from 1H OHLC, so this script backfills the missing evidence from Bitget's
public ``history-candles`` endpoint:

    [T0 - 72h, T0 + 48h] at 1m, per signal

Output is written outside git (default ``data/1m/``), one JSON file per signal
plus ``MANIFEST.json``. No API keys are used. The first run is intentionally
paged slowly (8 req/s) and resumable; existing files are skipped unless
``--force`` is passed.

Examples:
    python scripts/fetch_1m_candles.py --limit 3
    python scripts/fetch_1m_candles.py --symbols PUMP,WLD,ENA
    python scripts/fetch_1m_candles.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.market.bitget import BitgetPublicMarketClient

CORPUS_DIR = REPO_ROOT / "benchmarks" / "corpus"
DEFAULT_OUT = REPO_ROOT / "data" / "1m"


def _signal_window(signal: dict[str, Any], candle_row: dict[str, Any]) -> tuple[int, int] | None:
    t0_ms = candle_row.get("t0_ms")
    if t0_ms is None:
        stamp = signal.get("received_at") or signal.get("created_at")
        if not stamp:
            return None
        t0_ms = int(datetime.fromisoformat(stamp).timestamp() * 1000)
    start_ms = int(t0_ms) - 72 * 3600 * 1000
    end_ms = int(t0_ms) + 48 * 3600 * 1000
    return start_ms, end_ms


def _row_payload(signal: dict[str, Any], candles: list[Any], start_ms: int, end_ms: int) -> dict[str, Any]:
    rows = [
        [
            int(candle.timestamp_utc.timestamp() * 1000),
            str(candle.open),
            str(candle.high),
            str(candle.low),
            str(candle.close),
            str(candle.volume),
        ]
        for candle in candles
    ]
    return {
        "signal_id": signal["id"],
        "symbol": signal["pair_token"],
        "direction": signal["direction"],
        "telegram_msg_num": signal.get("telegram_msg_num"),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "resolution": "1m",
        "rows": len(rows),
        "candles": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N signals.")
    parser.add_argument("--latest", type=int, default=0, help="Only process the newest N signals.")
    parser.add_argument("--symbols", default="", help="Comma-separated base symbols (e.g. PUMP,WLD).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="Refetch files that already exist.")
    args = parser.parse_args(argv)

    signals = json.loads((CORPUS_DIR / "canonical_signals.json").read_text(encoding="utf-8"))
    candle_rows = json.loads(
        (CORPUS_DIR / "real_1h_candles_by_signal.json").read_text(encoding="utf-8")
    )
    by_id = {row["signal_id"]: row for row in candle_rows}
    wanted = {symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()}

    selected = [
        signal
        for signal in signals
        if not wanted or signal["pair_token"].replace("USDT", "").upper() in wanted
    ]
    selected.sort(key=lambda signal: signal.get("received_at") or signal.get("created_at") or "")
    if args.latest > 0:
        selected = selected[-args.latest :]
    elif args.limit > 0:
        selected = selected[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    client = BitgetPublicMarketClient()
    manifest: list[dict[str, Any]] = []
    fetched = 0

    for index, signal in enumerate(selected, start=1):
        window = _signal_window(signal, by_id.get(signal["id"], {}))
        if window is None:
            print(f"[{index}/{len(selected)}] {signal['pair_token']}: no T0, skipped")
            continue
        start_ms, end_ms = window
        target = args.out / f"{signal['id']}.json"
        if target.exists() and not args.force:
            print(f"[{index}/{len(selected)}] {signal['pair_token']}: exists, skipped")
            manifest.append(
                {"signal_id": signal["id"], "symbol": signal["pair_token"], "path": target.name}
            )
            continue

        candles = client.fetch_candle_range(signal["pair_token"], "1m", start_ms, end_ms)
        payload = _row_payload(signal, candles, start_ms, end_ms)
        target.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.append(
            {
                "signal_id": signal["id"],
                "symbol": signal["pair_token"],
                "path": target.name,
                "rows": payload["rows"],
                "sha256": digest,
            }
        )
        fetched += 1
        print(
            f"[{index}/{len(selected)}] {signal['pair_token']} "
            f"{signal['telegram_msg_num']}: {payload['rows']} bars -> {target.name}"
        )

    manifest_path = args.out / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "resolution": "1m",
                "signals_requested": len(selected),
                "signals_fetched": fetched,
                "files": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {manifest_path} ({len(manifest)} rows)")
    return 0 if fetched or manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())
