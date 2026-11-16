"""Bulk Bitget USDT-FUTURES research panel fetcher (`scripts/fetch_research_panel.py`).

Download a multi-year 4H panel for every liquid perpetual, so research no
longer depends on the 95-setup Telegram corpus (which covers nine weeks and one
regime). The public ``history-candles`` endpoint pages backwards with
``endTime``; this script walks each symbol back to ``--start``, deduplicates,
and writes one JSONL file per symbol plus a manifest with SHA-256 hashes.

Designed to run unchanged on the workstation (through the SSH relay) or on the
VPS (direct egress). Stdlib only: no project imports, no credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_URL = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
USER_AGENT = "ProteusResearchPanel/1.0"

# Fiat, stable, and non-crypto quotes that are not part of the crypto panel.
NON_CRYPTO_BASE = {
    "USDC", "USDT", "FDUSD", "TUSD", "DAI", "USDE", "EUR", "GBP", "JPY",
    "BRL", "TRY", "AUD", "CAD", "CHF", "CNH", "HKD", "IDR", "INR", "KRW",
    "MXN", "NGN", "NZD", "PHP", "PLN", "RUB", "SEK", "SGD", "THB", "UAH",
    "VND", "ZAR",
}

# Majors and historically important contracts worth probing even when their
# current volume is low or zero. Delisted symbols simply return no rows.
EXTRA_PROBE = (
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "MATIC", "LTC", "BCH", "TRX", "ATOM", "ETC", "FIL", "NEAR", "APT", "ARB",
    "OP", "SUI", "SEI", "TIA", "INJ", "AAVE", "UNI", "MKR", "CRV", "SAND",
    "MANA", "AXS", "GALA", "APE", "FTM", "ALGO", "EGLD", "THETA", "FTT",
    "LUNA", "LUNA2", "USTC", "WAVES", "KSM", "COMP", "SNX", "YFI", "SUSHI",
    "1INCH", "ZEC", "DASH", "XMR", "ENS", "LDO", "RPL", "PEPE", "SHIB",
    "WLD", "ENA", "PENGU", "MAGIC", "QNT", "TRUMP", "GRASS", "NOT", "FLOKI",
    "ETHFI", "TAO", "PENDLE", "ICP", "IOST", "HBAR", "BOME", "ONDO", "ZRO",
    "PUMP", "ASTER", "EUL", "PONS", "GIGGLE", "NIL", "STONK", "VVV", "RARE",
    "GRIFFAIN", "POWER", "ZAMA", "UAI", "EVAA", "LIT", "SNDK", "XAU", "SOXL",
)


class TokenBucket:
    """Process-wide average request-rate limiter."""

    def __init__(self, rate_per_second: float, burst: int | None = None) -> None:
        self.rate = max(0.1, float(rate_per_second))
        self.capacity = float(max(1, burst if burst is not None else int(self.rate)))
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity, self._tokens + (now - self._updated) * self.rate
                )
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                delay = (1.0 - self._tokens) / self.rate
            time.sleep(delay)


BUCKET: TokenBucket = TokenBucket(8.0)


def get_json(path: str, attempts: int = 5, timeout: float = 20.0) -> dict[str, Any]:
    url = path if path.startswith("http") else BASE_URL + path
    last_error: Exception | None = None
    for attempt in range(attempts):
        BUCKET.acquire()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in (429, 500, 502, 503, 504):
                retry_after = error.headers.get("Retry-After")
                delay = min(30.0, float(retry_after)) if retry_after else 0.5 * (2**attempt)
                time.sleep(delay + random.random() * 0.3)
                continue
            return {"code": str(error.code), "msg": str(error), "data": None}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.5 * (2**attempt) + random.random() * 0.3)
    return {"code": "error", "msg": str(last_error), "data": None}


def parse_start(value: str) -> int:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        stamp = datetime.fromisoformat(f"{value}T00:00:00+00:00")
    else:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    return int(stamp.timestamp() * 1000)


def to_base(symbol: str) -> str:
    return symbol.upper().removesuffix("USDT")


def select_universe(top: int, min_volume_usdt: float) -> tuple[list[str], dict[str, Any]]:
    tickers_payload = get_json(f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}")
    contracts_payload = get_json(f"/api/v2/mix/market/contracts?productType={PRODUCT_TYPE}")
    tickers = {
        row["symbol"]: row
        for row in (tickers_payload.get("data") or [])
        if isinstance(row, dict) and row.get("symbol", "").endswith("USDT")
    }
    contracts = {
        row["symbol"]: row
        for row in (contracts_payload.get("data") or [])
        if isinstance(row, dict)
    }

    ranked: list[tuple[str, float]] = []
    for symbol, row in tickers.items():
        base = to_base(symbol)
        if base in NON_CRYPTO_BASE:
            continue
        contract = contracts.get(symbol, {})
        if str(contract.get("isRwa", "false")).lower() == "true":
            continue
        try:
            volume = float(row.get("usdtVolume") or 0.0)
        except (TypeError, ValueError):
            continue
        if volume < min_volume_usdt:
            continue
        ranked.append((symbol, volume))
    ranked.sort(key=lambda item: item[1], reverse=True)

    selected = [symbol for symbol, _ in ranked[:top]]
    for base in EXTRA_PROBE:
        symbol = f"{base}USDT"
        if symbol in tickers and symbol not in selected:
            selected.append(symbol)
    for required in ("BTCUSDT", "ETHUSDT"):
        if required not in selected:
            selected.insert(0, required)

    diagnostics = {
        "tickers_total": len(tickers),
        "eligible_ranked": len(ranked),
        "selected": len(selected),
        "top_volume_usdt_millions": [
            [symbol, round(volume / 1e6, 1)] for symbol, volume in ranked[:15]
        ],
    }
    return selected, diagnostics


def fetch_symbol(
    symbol: str,
    granularity: str,
    start_ms: int,
    end_ms: int,
    page_limit: int = 200,
    max_pages: int = 400,
) -> tuple[list[list[str]], str | None]:
    collected: dict[int, list[str]] = {}
    cursor = int(end_ms)
    pages = 0
    while cursor > start_ms and pages < max_pages:
        payload = get_json(
            f"/api/v2/mix/market/history-candles?symbol={symbol}"
            f"&productType={PRODUCT_TYPE}&granularity={granularity}"
            f"&limit={page_limit}&endTime={cursor}"
        )
        rows = payload.get("data")
        if not isinstance(rows, list) or not rows:
            if pages == 0:
                return [], f"{payload.get('code')}: {payload.get('msg')}"
            break
        oldest = cursor
        added = 0
        for row in rows:
            try:
                stamp = int(row[0])
            except (TypeError, ValueError, IndexError):
                continue
            oldest = min(oldest, stamp)
            if start_ms <= stamp <= end_ms and stamp not in collected:
                collected[stamp] = row
                added += 1
        pages += 1
        if oldest <= start_ms or added == 0 or oldest >= cursor:
            break
        cursor = oldest - 1
    return [collected[stamp] for stamp in sorted(collected)], None


def write_jsonl(path: Path, rows: list[list[str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            line = json.dumps(
                {
                    "ts": int(row[0]),
                    "o": float(row[1]),
                    "h": float(row[2]),
                    "l": float(row[3]),
                    "c": float(row[4]),
                    "v": float(row[5]) if len(row) > 5 else 0.0,
                },
                separators=(",", ":"),
            )
            digest.update(line.encode("utf-8"))
            handle.write(line + "\n")
    os.replace(temp, path)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/research", help="output directory")
    parser.add_argument("--start", default="2021-01-01", help="earliest UTC date to keep")
    parser.add_argument("--top", type=int, default=140, help="top symbols by 24h USDT volume")
    parser.add_argument("--min-volume", type=float, default=1_000_000.0)
    parser.add_argument("--granularity", default="4H")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--rps", type=float, default=8.0)
    parser.add_argument("--symbols", default="", help="force a comma-separated symbol list")
    args = parser.parse_args(argv)

    global BUCKET
    BUCKET = TokenBucket(args.rps)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    start_ms = parse_start(args.start)
    end_ms = int(time.time() * 1000)

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        diagnostics: dict[str, Any] = {"forced_symbols": len(symbols)}
    else:
        symbols, diagnostics = select_universe(args.top, args.min_volume)

    print(f"fetching {len(symbols)} symbols from {args.start} ({args.granularity})", flush=True)
    (out_dir / "universe.json").write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "granularity": args.granularity,
                "start": args.start,
                "diagnostics": diagnostics,
                "symbols": symbols,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def work(symbol: str) -> dict[str, Any]:
        rows, error = fetch_symbol(symbol, args.granularity, start_ms, end_ms)
        record: dict[str, Any] = {
            "symbol": symbol,
            "rows": len(rows),
            "first_ts": int(rows[0][0]) if rows else None,
            "last_ts": int(rows[-1][0]) if rows else None,
            "error": error,
        }
        if rows:
            path = out_dir / args.granularity.lower() / f"{symbol}.jsonl"
            record["sha256"] = write_jsonl(path, rows)
        with lock:
            results.append(record)
            done = len(results)
            if done % 10 == 0 or done == len(symbols):
                print(f"  {done}/{len(symbols)} symbols", flush=True)
        return record

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, symbol) for symbol in symbols]
        for future in as_completed(futures):
            future.result()

    results.sort(key=lambda item: item["symbol"])
    usable = [row for row in results if row["rows"]]
    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": "Bitget public /api/v2/mix/market/history-candles",
        "granularity": args.granularity,
        "requested_start": args.start,
        "requested_end_ms": end_ms,
        "symbols_requested": len(symbols),
        "symbols_with_data": len(usable),
        "rows_total": sum(row["rows"] for row in results),
        "diagnostics": diagnostics,
        "symbols": results,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"done: {len(usable)}/{len(symbols)} symbols, "
        f"{manifest['rows_total']:,} bars -> {out_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
