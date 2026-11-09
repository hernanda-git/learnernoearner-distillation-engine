"""Rate-limit, retry and transport tests for the public Bitget client."""

from __future__ import annotations

import json
import urllib.error
from decimal import Decimal
from typing import Self

from proteus.market import bitget


class _FakeResp:
    def __init__(self, payload: dict[str, object]) -> None:
        self.status = 200
        self._raw = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _payload(rows: list[list[str]]) -> dict[str, object]:
    return {"code": "00000", "msg": "success", "data": rows}


def _row(ts_ms: int = 1_700_000_000_000, price: str = "2.0") -> list[str]:
    return [str(ts_ms), price, price, price, price, "1.0"]


def _url(req: object, fallback: str = "") -> str:
    return getattr(req, "full_url", fallback)


def _client(**kwargs: object) -> bitget.BitgetPublicMarketClient:
    base: dict[str, object] = {
        "rate_limit_rps": 1000.0,
        "max_workers": 2,
        "max_attempts": 3,
        "timeout": 1.0,
        "ssh_relay_host": None,
        "cache": bitget._TTLCache(),
    }
    base.update(kwargs)
    return bitget.BitgetPublicMarketClient(**base)


def test_bitget_client_retries_on_429_and_honours_retry_after(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(bitget.time, "sleep", lambda seconds: sleeps.append(seconds))

    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(_url(req))
        if len(calls) <= 2:
            raise urllib.error.HTTPError(_url(req), 429, "Too Many", {}, None)
        return _FakeResp(_payload([_row(price="2.5")]))

    monkeypatch.setattr(bitget.urllib.request, "urlopen", fake_urlopen)

    candles = _client().fetch_candles("WLD", "4H", 18)

    assert len(calls) == 3, "429 must be retried, not surfaced as empty data"
    assert len(candles) == 1
    assert candles[0].close == Decimal("2.5")
    assert sleeps and sleeps[0] > 0.0, "retry path must apply exponential backoff"


def test_bitget_client_batch_deduplicates_and_caches(monkeypatch) -> None:
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(_url(req))
        return _FakeResp(_payload([_row()]))

    monkeypatch.setattr(bitget.urllib.request, "urlopen", fake_urlopen)

    client = _client()
    result = client.fetch_candles_batch(
        [("WLD", "4H", 18), ("WLD", "4H", 18), ("PEPE", "15m", 12)]
    )

    assert len(calls) == 2, "identical specs must collapse to one request"
    assert set(result) == {("WLD", "4H"), ("PEPE", "15m")}
    assert all(len(series) == 1 for series in result.values())

    client.fetch_candles_batch([("WLD", "4H", 18)])
    assert len(calls) == 2, "repeated scans inside the TTL must hit the cache"


def test_bitget_client_falls_back_to_one_batched_ssh_relay(monkeypatch) -> None:
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("direct egress blocked")

    monkeypatch.setattr(bitget.urllib.request, "urlopen", fake_urlopen)

    relay_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        relay_calls.append(cmd)
        stdout = (
            "noise\n"
            + json.dumps(_payload([_row()]))
            + f"\n{bitget.RELAY_SENTINEL}\n"
            + json.dumps(_payload([_row()]))
            + f"\n{bitget.RELAY_SENTINEL}\n"
        )

        class _Completed:
            def __init__(self) -> None:
                self.stdout = stdout
                self.returncode = 0

        return _Completed()

    monkeypatch.setattr(bitget.subprocess, "run", fake_run)

    client = _client(ssh_relay_host="relay@example")
    result = client.fetch_candles_batch([("WLD", "4H", 18), ("PEPE", "15m", 12)])

    assert client.direct_available is False
    assert len(relay_calls) == 1, "the whole batch must ride one SSH command"
    assert len(result[("WLD", "4H")]) == 1
    assert len(result[("PEPE", "15m")]) == 1


def test_bitget_client_returns_empty_on_exchange_error_code(monkeypatch) -> None:
    def fake_urlopen(req, timeout=None):
        return _FakeResp({"code": "40015", "msg": "invalid symbol"})

    monkeypatch.setattr(bitget.urllib.request, "urlopen", fake_urlopen)

    assert _client().fetch_candles("NOPE", "4H", 18) == []
