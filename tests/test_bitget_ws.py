"""Websocket candle-stream and scanner-fallback tests."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from proteus.domain.models import Candle
from proteus.market.bitget_ws import BitgetCandleStream, candle_from_push, upsert_candle
from proteus.shadow import ForwardShadowScanner


def _candle(
    minutes_ago: int = 0, close: str = "2.0", symbol: str = "WLD", granularity: str = "15m"
) -> Candle:
    ts = datetime(2026, 11, 9, 12, 0, tzinfo=UTC) - timedelta(minutes=minutes_ago)
    return Candle(
        symbol=symbol,
        timeframe=granularity,
        timestamp_utc=ts,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal(1),
    )


def _row(ts: datetime, price: str = "2.05") -> list[str]:
    return [
        str(int(ts.timestamp() * 1000)),
        price,
        price,
        price,
        price,
        "10",
        "20",
        "20",
    ]


def test_upsert_candle_replaces_forms_appends_trims_and_handles_late_bars() -> None:
    series: list[Candle] = []
    first = _candle(minutes_ago=15, close="1.0")
    forming = _candle(minutes_ago=0, close="1.1")
    upsert_candle(series, first, max_bars=2)
    upsert_candle(series, forming, max_bars=2)
    assert [c.close for c in series] == [Decimal("1.0"), Decimal("1.1")]

    upsert_candle(series, _candle(minutes_ago=0, close="1.2"), max_bars=2)
    assert len(series) == 2 and series[-1].close == Decimal("1.2")

    upsert_candle(series, _candle(minutes_ago=15, close="1.05"), max_bars=2)
    assert series[0].close == Decimal("1.05"), "late pushes must patch, not duplicate"

    upsert_candle(series, _candle(minutes_ago=-15, close="1.3"), max_bars=2)
    assert [c.close for c in series] == [Decimal("1.2"), Decimal("1.3")], "oldest bar must trim"


def test_candle_from_push_parses_and_rejects_malformed_rows() -> None:
    ts = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    candle = candle_from_push("WLD", "15m", _row(ts))
    assert candle is not None
    assert candle.timestamp_utc == ts
    assert candle.close == Decimal("2.05")
    assert candle_from_push("WLD", "15m", ["not-a-time"]) is None


def test_shards_respect_bitget_channel_and_message_limits() -> None:
    specs = [
        ("WLD", "4H", 18),
        ("WLD", "15m", 12),
        ("PEPE", "4H", 18),
        ("PEPE", "15m", 12),
        ("BTCUSDT", "1Dutc", 5),
    ]
    stream = BitgetCandleStream(specs, connections=2, connect_factory=object())

    shards = stream._shards()

    assert len(shards) == 2
    assert all(len(shard) <= 46 for shard in shards), "Bitget warns above ~50 channels/connection"
    chans = [arg for shard in shards for arg in shard]
    assert len(chans) == len(specs)
    assert {c["instId"] for c in chans} == {"WLDUSDT", "PEPEUSDT", "BTCUSDT"}
    assert {c["channel"] for c in chans} == {"candle4H", "candle15m", "candle1Dutc"}
    assert all(c["instType"] == "USDT-FUTURES" for c in chans)


def test_series_for_omits_stale_series_and_trims_to_limit() -> None:
    stream = BitgetCandleStream([("WLD", "15m", 2)], connect_factory=object())
    stream._series[("WLD", "15m")] = [_candle(minutes_ago=30), _candle(minutes_ago=15), _candle()]
    stream._pushed_at[("WLD", "15m")] = time.monotonic()

    fresh = stream.series_for([("WLD", "15m", 2)])
    assert len(fresh[("WLD", "15m")]) == 2

    stream._pushed_at[("WLD", "15m")] = time.monotonic() - 3600
    assert stream.series_for([("WLD", "15m", 2)]) == {}, "stale bars must fall back to REST"


def test_handle_applies_subscribed_push_only() -> None:
    stream = BitgetCandleStream([("WLD", "15m", 12)], connect_factory=object())
    stream._inst_symbol["WLDUSDT"] = "WLD"
    ts = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    stream._handle(
        json.dumps(
            {
                "action": "update",
                "arg": {"channel": "candle15m", "instId": "WLDUSDT"},
                "data": [_row(ts)],
            }
        )
    )
    series = stream.series_for([("WLD", "15m", 12)])[("WLD", "15m")]
    assert len(series) == 1 and series[0].close == Decimal("2.05")

    # Unknown instId / non-candle channel must be ignored, not crash.
    stream._handle(json.dumps({"action": "update", "arg": {"channel": "ticker", "instId": "X"}}))
    stream._handle("not json")


def test_scanner_only_pays_rest_for_series_the_stream_cannot_serve() -> None:
    candle = _candle()

    class _FakeStream:
        def series_for(self, specs):
            return {("WLD", "4H"): [candle], ("WLD", "15m"): [candle]}

    class _FakeClient:
        def __init__(self) -> None:
            self.calls: list[list[tuple[str, str, int]]] = []

        def fetch_candles_batch(self, specs):
            self.calls.append(list(specs))
            return {(symbol, granularity): [] for symbol, granularity, _ in specs}

    scanner = ForwardShadowScanner.__new__(ForwardShadowScanner)
    scanner.stream = _FakeStream()
    scanner.client = _FakeClient()

    result = scanner._resolve_series(
        [("WLD", "4H", 18), ("WLD", "15m", 12), ("BTCUSDT", "1Dutc", 5)]
    )

    assert result[("WLD", "4H")] == [candle]
    assert result[("BTCUSDT", "1Dutc")] == []
    assert scanner.client.calls == [[("BTCUSDT", "1Dutc", 5)]]


def test_build_requests_spec_covers_compass_and_universe() -> None:
    spec = ForwardShadowScanner.build_requests_spec(("WLD", "PEPE"))
    assert spec[:2] == [("BTCUSDT", "1Dutc", 5), ("ETHUSDT", "1Dutc", 5)]
    assert len(spec) == 6
    assert ("WLD", "4H", 18) in spec and ("PEPE", "15m", 12) in spec


def _push(channel: str, inst_id: str, ts: datetime, price: str = "2.05") -> str:
    return json.dumps(
        {
            "action": "update",
            "arg": {"channel": channel, "instId": inst_id},
            "data": [_row(ts, price)],
        }
    )


def test_upsert_reports_only_new_bars() -> None:
    series = [_candle(minutes_ago=15)]
    assert upsert_candle(series, _candle(minutes_ago=15, close="1.1"), 12) is False
    assert upsert_candle(series, _candle(), 12) is True
    assert upsert_candle(series, _candle(close="1.2"), 12) is False


def test_only_15m_roll_wakes_close_waiters() -> None:
    stream = BitgetCandleStream(
        [("WLD", "15m", 12), ("WLD", "4H", 18)], connect_factory=object()
    )
    stream._inst_symbol["WLDUSDT"] = "WLD"
    t0 = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    stream._handle(_push("candle15m", "WLDUSDT", t0))
    stream._handle(_push("candle4H", "WLDUSDT", t0))
    assert stream.close_seq == 0, "the first bar is an open, not a close"
    assert stream.wait_for_close(0, timeout=0.01) == (False, 0)

    stream._handle(_push("candle4H", "WLDUSDT", t0 + timedelta(hours=4)))
    assert stream.close_seq == 0, "4H rolls must not wake 15m close waiters"

    stream._handle(_push("candle15m", "WLDUSDT", t0 + timedelta(minutes=15)))
    assert stream.close_seq == 1
    assert stream.wait_for_close(0, timeout=0.01) == (True, 1)
