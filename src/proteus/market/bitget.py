"""Rate-limited public Bitget USDT-FUTURES candle client (`proteus.market.bitget`).

Bitget documents a 20 requests/second per-IP ceiling on
``GET /api/v2/mix/market/candles`` and answers HTTP 429 once it is exceeded.
This client keeps the engine well below that ceiling with a process-wide token
bucket, honours ``Retry-After``, retries transient failures with jittered
exponential backoff, and falls back to one batched SSH relay when the local
egress IP cannot reach ``api.bitget.com`` directly (the workstation case; the
production daemon on the VPS always uses the direct path).
"""

from __future__ import annotations

import json
import os
import random
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from proteus.domain.models import Candle

CANDLES_URL = "https://api.bitget.com/api/v2/mix/market/candles"
USER_AGENT = "ProteusDistillationEngine/0.1"
RELAY_SENTINEL = "@@@PROTEUS@@@"

# Bitget allows 20 req/s/IP; stay at 40% of it so retries and other clients fit.
DEFAULT_RATE_LIMIT_RPS = 8.0
DEFAULT_TIMEOUT_SECONDS = 6.0
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_MAX_WORKERS = 4
DEFAULT_BACKOFF_SECONDS = 0.5
RATE_LIMIT_COOLDOWN_SECONDS = 5.0
RELAY_RETRY_AFTER_SECONDS = 600.0

# The last candle of every series is still forming, so a short cache only
# deduplicates UI-triggered scans that land inside the same daemon cycle.
_CACHE_TTL_SECONDS: dict[str, float] = {
    "1m": 15.0,
    "5m": 30.0,
    "15m": 60.0,
    "1H": 60.0,
    "4H": 60.0,
    "1D": 120.0,
    "1Dutc": 120.0,
}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class TokenBucket:
    """Thread-safe token bucket enforcing an average request rate with a bounded burst."""

    def __init__(self, rate_per_second: float, burst: int | None = None) -> None:
        self.rate = max(0.1, float(rate_per_second))
        self.capacity = float(max(1, burst if burst is not None else int(self.rate)))
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a token is available and return the seconds spent waiting."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._updated
                self._updated = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return waited
                delay = (1.0 - self._tokens) / self.rate
            time.sleep(delay)
            waited += delay


class _TTLCache:
    """Small thread-safe TTL cache keyed by (pair, granularity, limit)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, int], tuple[float, list[Candle]]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str, int]) -> list[Candle] | None:
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                return None
            expires_at, candles = row
            if time.monotonic() >= expires_at:
                self._rows.pop(key, None)
                return None
            return candles

    def set(self, key: tuple[str, str, int], candles: list[Candle], ttl: float) -> None:
        with self._lock:
            self._rows[key] = (time.monotonic() + ttl, candles)

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()


_CANDLE_CACHE = _TTLCache()


def clear_candle_cache() -> None:
    _CANDLE_CACHE.clear()


def _candles_url(pair: str, granularity: str, limit: int) -> str:
    return (
        f"{CANDLES_URL}?symbol={pair}&productType=USDT-FUTURES"
        f"&granularity={granularity}&limit={int(limit)}"
    )


def _to_candles(payload: dict[str, Any] | None, symbol: str, granularity: str) -> list[Candle]:
    if not payload or payload.get("code") != "00000":
        return []
    series: list[Candle] = []
    for row in payload.get("data", []):
        try:
            ts_ms = int(row[0])
            series.append(
                Candle(
                    symbol=symbol,
                    timeframe=granularity,
                    timestamp_utc=datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC),
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    volume=Decimal(str(row[5])),
                )
            )
        except (TypeError, ValueError, IndexError):
            continue
    series.sort(key=lambda c: c.timestamp_utc)
    return series


class BitgetPublicMarketClient:
    """Public, API-key-free Bitget candle reader with rate-limit protection."""

    def __init__(
        self,
        rate_limit_rps: float | None = None,
        max_workers: int | None = None,
        max_attempts: int | None = None,
        timeout: float | None = None,
        ssh_relay_host: str | None = "valarion@46.202.155.192",
        cache: _TTLCache | None = None,
    ) -> None:
        self.rate_limit_rps = rate_limit_rps or _env_float(
            "BITGET_RATE_LIMIT_RPS", DEFAULT_RATE_LIMIT_RPS
        )
        self.max_workers = max_workers or _env_int("BITGET_MAX_WORKERS", DEFAULT_MAX_WORKERS)
        self.max_attempts = max(1, max_attempts or _env_int("BITGET_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS))
        self.timeout = timeout or _env_float("BITGET_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        self.ssh_relay_host = ssh_relay_host
        self._bucket = TokenBucket(self.rate_limit_rps)
        self._cache = cache if cache is not None else _CANDLE_CACHE
        self._consecutive_429 = 0
        self.direct_available: bool | None = None
        self._relay_until = 0.0

    # -- retry / backoff -----------------------------------------------------

    @staticmethod
    def _retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
        raw = exc.headers.get("Retry-After") if exc.headers else None
        if not raw:
            return None
        try:
            return max(0.0, min(30.0, float(raw)))
        except ValueError:
            return None

    def _get_json(
        self, url: str, attempts: int | None = None
    ) -> tuple[dict[str, Any] | None, int | None]:
        """Return (payload, http_status); never raises. ``(None, None)`` means network failure."""
        attempts = max(1, attempts or self.max_attempts)
        delay = DEFAULT_BACKOFF_SECONDS
        last_status: int | None = None

        for attempt in range(1, attempts + 1):
            self._bucket.acquire()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = int(getattr(resp, "status", 200) or 200)
                    raw = resp.read().decode("utf-8")
                self._consecutive_429 = 0
                try:
                    return json.loads(raw), status
                except json.JSONDecodeError:
                    return None, status
            except urllib.error.HTTPError as exc:
                last_status = exc.code
                if exc.code == 429:
                    self._consecutive_429 += 1
                    if self._consecutive_429 >= 3:
                        time.sleep(RATE_LIMIT_COOLDOWN_SECONDS)
                        self._consecutive_429 = 0
                    if attempt == attempts:
                        return None, exc.code
                    wait = self._retry_after_seconds(exc)
                    time.sleep((wait if wait is not None else delay) * (1.0 + 0.25 * random.random()))
                    delay = min(8.0, delay * 2.0)
                    continue
                if 500 <= exc.code < 600:
                    if attempt == attempts:
                        return None, exc.code
                    time.sleep(delay * (1.0 + 0.25 * random.random()))
                    delay = min(8.0, delay * 2.0)
                    continue
                return None, exc.code
            except Exception:  # noqa: BLE001 - any transport failure must fall back, never crash
                if attempt == attempts:
                    return None, None
                time.sleep(delay * (1.0 + 0.25 * random.random()))
                delay = min(8.0, delay * 2.0)

        return None, last_status

    # -- direct + relay transports ------------------------------------------

    def _can_use_direct(self) -> bool:
        return not (self.direct_available is False and time.monotonic() < self._relay_until)

    def _mark_direct_unavailable(self) -> None:
        self.direct_available = False
        self._relay_until = time.monotonic() + RELAY_RETRY_AFTER_SECONDS

    def _fetch_direct_many(self, urls: list[str]) -> list[dict[str, Any] | None]:
        if not urls:
            return []
        workers = min(self.max_workers, len(urls))

        def _one(url: str) -> dict[str, Any] | None:
            return self._get_json(url)[0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(_one, urls))

    def _fetch_via_relay(self, urls: list[str]) -> list[dict[str, Any] | None]:
        if not self.ssh_relay_host or not urls:
            return [None] * len(urls)
        script = " ; ".join(
            f"curl -s --max-time {int(self.timeout)} {shlex.quote(url)}"
            f"; printf '\\n{RELAY_SENTINEL}\\n'"
            for url in urls
        )
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            self.ssh_relay_host,
            script,
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=max(60.0, len(urls) * (self.timeout + 1.0)),
            )
        except Exception:  # noqa: BLE001 - relay is best-effort; degrade to empty series
            return [None] * len(urls)

        chunks = res.stdout.split(RELAY_SENTINEL)
        payloads: list[dict[str, Any] | None] = []
        for chunk in chunks:
            chunk = chunk.strip()
            payload: dict[str, Any] | None = None
            for line in reversed(chunk.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        payload = None
                    break
            payloads.append(payload)
        payloads = payloads[: len(urls)]
        payloads.extend([None] * (len(urls) - len(payloads)))
        return payloads

    # -- public API ----------------------------------------------------------

    def fetch_candles(
        self,
        symbol: str,
        granularity: str = "15m",
        limit: int = 32,
    ) -> list[Candle]:
        return self.fetch_candles_batch([(symbol, granularity, limit)]).get(
            (symbol, granularity), []
        )

    def fetch_candles_batch(
        self,
        requests_spec: Sequence[tuple[str, str, int]],
    ) -> dict[tuple[str, str], list[Candle]]:
        """Fetch many (symbol, granularity, limit) series with caching and rate limiting."""
        results: dict[tuple[str, str], list[Candle]] = {}
        if not requests_spec:
            return results

        # Deduplicate identical specs while preserving order.
        specs: list[tuple[str, str, int]] = []
        seen: set[tuple[str, str, int]] = set()
        for sym, gran, lim in requests_spec:
            spec = (sym, gran, int(lim))
            if spec in seen:
                continue
            seen.add(spec)
            specs.append(spec)

        pending: list[tuple[str, str, int]] = []
        urls: list[str] = []
        for sym, gran, lim in specs:
            key = (sym, gran, lim)
            cached = self._cache.get(key)
            if cached is not None:
                results[(sym, gran)] = cached
                continue
            pair = sym.upper().replace("/", "")
            if not pair.endswith("USDT"):
                pair = f"{pair}USDT"
            pending.append((sym, gran, lim))
            urls.append(_candles_url(pair, gran, lim))

        if not pending:
            return results

        payloads: list[dict[str, Any] | None]
        if self._can_use_direct():
            first_payload, first_status = self._get_json(urls[0], attempts=1)
            if first_payload is None and first_status is None:
                # Direct egress is blocked; relay the whole batch and remember it.
                self._mark_direct_unavailable()
                payloads = self._fetch_via_relay(urls)
            else:
                # Direct egress works. Reuse a clean probe payload; otherwise
                # refetch every URL so a 429/5xx probe gets the full retry policy.
                self.direct_available = True
                if first_payload is not None and first_status == 200:
                    payloads = [first_payload] + self._fetch_direct_many(urls[1:])
                else:
                    payloads = self._fetch_direct_many(urls)
        else:
            payloads = self._fetch_via_relay(urls)

        for (sym, gran, lim), payload in zip(pending, payloads):
            candles = _to_candles(payload, sym, gran)
            results[(sym, gran)] = candles
            self._cache.set((sym, gran, lim), candles, _CACHE_TTL_SECONDS.get(gran, 60.0))

        return results
