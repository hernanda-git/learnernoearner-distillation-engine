"""Persistent Bitget public candlestick stream (`proteus.market.bitget_ws`).

Replaces steady-state REST polling: one REST bootstrap, then a small set of
public WebSocket connections keep every 4H/15m/1Dutc series current. Bitget
recommends fewer than 50 channels per connection, so the 92 subscriptions are
sharded across two connections. If ``websockets`` is not installed or the
stream has not produced a fresh bar, callers fall back to the REST client.

Bitget candlestick channel: ``candle4H``, ``candle15m``, ``candle1Dutc`` on
``USDT-FUTURES``. Pushes are ``{"action": "snapshot"|"update", "arg": {...},
"data": [[ts, o, h, l, c, baseVol, quoteVol, usdtVol], ...]}``. The server
drops a connection after 2 minutes without a text ``"ping"``.
"""

from __future__ import annotations

import json
import random
import threading
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from proteus.domain.models import Candle
from proteus.market.bitget import BitgetPublicMarketClient

try:  # optional dependency: the engine must still run REST-only without it
    from websockets.sync.client import connect as _ws_connect
except ImportError:  # pragma: no cover - exercised on hosts without the extra
    _ws_connect = None  # type: ignore[assignment]

WS_PUBLIC_URL = "wss://ws.bitget.com/v2/ws/public"
MAX_CHANNELS_PER_CONNECTION = 46
MAX_ARGS_PER_MESSAGE = 40
PING_INTERVAL_SECONDS = 25.0
RECV_POLL_SECONDS = 1.0
RECONNECT_BASE_SECONDS = 1.0
RECONNECT_MAX_SECONDS = 30.0

# A series older than this is treated as unavailable so the scanner re-fetches
# it over REST. Bitget pushes at least once per bar even with zero trades.
FRESHNESS_SECONDS: dict[str, float] = {
    "1m": 15 * 60.0,
    "5m": 30 * 60.0,
    "15m": 45 * 60.0,
    "1H": 3 * 3600.0,
    "4H": 12 * 3600.0,
    "1D": 3 * 86400.0,
    "1Dutc": 3 * 86400.0,
}


def _pair(symbol: str) -> str:
    pair = symbol.upper().replace("/", "")
    return pair if pair.endswith("USDT") else f"{pair}USDT"


def _channel(granularity: str) -> str:
    return f"candle{granularity}"


def _chunks(rows: Sequence[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def upsert_candle(series: list[Candle], candle: Candle, max_bars: int) -> None:
    """Apply a pushed bar in place: replace the forming bar, append a new one, trim."""
    if series and series[-1].timestamp_utc == candle.timestamp_utc:
        series[-1] = candle
    elif series and candle.timestamp_utc < series[-1].timestamp_utc:
        for index in range(len(series) - 1, -1, -1):
            if series[index].timestamp_utc == candle.timestamp_utc:
                series[index] = candle
                break
    else:
        series.append(candle)
    if len(series) > max_bars:
        del series[: len(series) - max_bars]


def candle_from_push(symbol: str, granularity: str, row: Sequence[str]) -> Candle | None:
    try:
        return Candle(
            symbol=symbol,
            timeframe=granularity,
            timestamp_utc=datetime.fromtimestamp(int(row[0]) / 1000.0, tz=UTC),
            open=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            volume=Decimal(str(row[5])),
        )
    except (TypeError, ValueError, IndexError):
        return None


class BitgetCandleStream:
    """Background websocket cache of Bitget candlestick series with REST fallback."""

    def __init__(
        self,
        requests_spec: Sequence[tuple[str, str, int]],
        rest_client: BitgetPublicMarketClient | None = None,
        connections: int = 2,
        connect_factory: Any | None = None,
    ) -> None:
        self._specs = list(dict.fromkeys((s, g, int(n)) for s, g, n in requests_spec))
        self._rest = rest_client or BitgetPublicMarketClient()
        self._connections = max(1, connections)
        self._connect = connect_factory if connect_factory is not None else _ws_connect
        self._series: dict[tuple[str, str], list[Candle]] = {}
        self._pushed_at: dict[tuple[str, str], float] = {}
        self._inst_symbol: dict[str, str] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._started = False
        self.last_error: str | None = None
        self.connected_legs = 0

    # -- lifecycle -----------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._connect is not None

    @property
    def connections(self) -> int:
        return self._connections

    def start(self, bootstrap: bool = True) -> bool:
        """Bootstrap via REST, then open the subscription threads. Returns availability."""
        if not self.available or self._started:
            return self.available
        if bootstrap:
            self.bootstrap()
        for index, shard in enumerate(self._shards()):
            thread = threading.Thread(
                target=self._run_connection,
                args=(index, shard),
                name=f"bitget-ws-{index}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        self._started = True
        return True

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=3.0)
        self._threads.clear()
        self._started = False

    def bootstrap(self) -> None:
        """Seed all series from REST once; the stream only carries deltas afterwards."""
        try:
            fetched = self._rest.fetch_candles_batch(self._specs)
        except Exception as exc:  # noqa: BLE001 - bootstrap failure must not kill the daemon
            self.last_error = f"bootstrap:{exc!r}"
            return
        now = time.monotonic()
        with self._lock:
            for (symbol, granularity, limit) in self._specs:
                series = list(fetched.get((symbol, granularity), []))
                self._series[(symbol, granularity)] = series[-limit:]
                if series:
                    self._pushed_at[(symbol, granularity)] = now
                    self._inst_symbol[_pair(symbol)] = symbol

    # -- reads ---------------------------------------------------------------

    def series_for(
        self, requests_spec: Sequence[tuple[str, str, int]]
    ) -> dict[tuple[str, str], list[Candle]]:
        """Return only fresh series; stale or missing keys are omitted (caller falls back)."""
        now = time.monotonic()
        result: dict[tuple[str, str], list[Candle]] = {}
        with self._lock:
            for symbol, granularity, limit in requests_spec:
                key = (symbol, granularity)
                series = self._series.get(key)
                if not series:
                    continue
                pushed_at = self._pushed_at.get(key, 0.0)
                if now - pushed_at > FRESHNESS_SECONDS.get(granularity, 3600.0):
                    continue
                result[key] = list(series[-int(limit) :])
        return result

    # -- websocket loop ------------------------------------------------------

    def _shards(self) -> list[list[dict[str, str]]]:
        symbols: list[str] = []
        for symbol, _, _ in self._specs:
            if symbol not in symbols:
                symbols.append(symbol)
        shards: list[list[dict[str, str]]] = [[] for _ in range(min(self._connections, len(symbols)))]
        for index, symbol in enumerate(symbols):
            shard = shards[index % len(shards)]
            for spec_symbol, granularity, _ in self._specs:
                if spec_symbol == symbol:
                    shard.append(
                        {
                            "instType": "USDT-FUTURES",
                            "channel": _channel(granularity),
                            "instId": _pair(symbol),
                        }
                    )
        return shards

    def _run_connection(self, index: int, args: list[dict[str, str]]) -> None:
        backoff = RECONNECT_BASE_SECONDS
        while not self._stop.is_set():
            try:
                with self._connect(
                    WS_PUBLIC_URL, open_timeout=15, close_timeout=5, ping_interval=None
                ) as ws:
                    for batch in _chunks(args, MAX_ARGS_PER_MESSAGE):
                        ws.send(json.dumps({"op": "subscribe", "args": batch}))
                    with self._lock:
                        self.connected_legs += 1
                    backoff = RECONNECT_BASE_SECONDS
                    last_ping = time.monotonic()
                    while not self._stop.is_set():
                        if time.monotonic() - last_ping >= PING_INTERVAL_SECONDS:
                            ws.send("ping")
                            last_ping = time.monotonic()
                        try:
                            raw = ws.recv(timeout=RECV_POLL_SECONDS)
                        except TimeoutError:
                            continue
                        self._handle(raw)
            except Exception as exc:  # noqa: BLE001 - reconnect on any transport failure
                self.last_error = f"leg{index}:{exc!r}"
            finally:
                with self._lock:
                    self.connected_legs = max(0, self.connected_legs - 1)
            if self._stop.is_set():
                return
            time.sleep(backoff + random.random() * 0.5)
            backoff = min(RECONNECT_MAX_SECONDS, backoff * 2.0)

    def _handle(self, raw: str | bytes) -> None:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return
        action = payload.get("action")
        arg = payload.get("arg")
        if action not in ("snapshot", "update") or not isinstance(arg, dict):
            return
        channel = str(arg.get("channel", ""))
        inst_id = str(arg.get("instId", ""))
        if not channel.startswith("candle") or not inst_id:
            return
        granularity = channel[len("candle") :]
        with self._lock:
            symbol = self._inst_symbol.get(inst_id)
        if symbol is None:
            return
        limit = next(
            (n for s, g, n in self._specs if s == symbol and g == granularity), None
        )
        if limit is None:
            return
        rows = payload.get("data") or []
        now = time.monotonic()
        with self._lock:
            series = self._series.setdefault((symbol, granularity), [])
            for row in rows:
                candle = candle_from_push(symbol, granularity, row)
                if candle is not None:
                    upsert_candle(series, candle, limit)
            if rows:
                self._pushed_at[(symbol, granularity)] = now
