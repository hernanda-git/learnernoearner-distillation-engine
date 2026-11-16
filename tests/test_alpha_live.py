"""Live alpha ledger tests (`proteus.alpha.live`)."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from proteus.alpha.live import (
    AlphaLiveTrader,
    LivePosition,
    LiveState,
    snapshot_state,
)
from proteus.alpha.research import default_config
from proteus.domain.models import Candle


class FakeClient:
    """Deterministic public-market stand-in for the live trader."""

    def __init__(self, symbols: list[str], *, days: int = 260) -> None:
        self.symbols = symbols
        self.days = days
        self.requests = 0

    def get_json(self, path: str, attempts: int | None = None) -> dict:
        if "tickers" in path:
            return {
                "data": [
                    {"symbol": symbol, "usdtVolume": "50000000"} for symbol in self.symbols
                ]
            }
        if "contracts" in path:
            return {
                "data": [
                    {"symbol": symbol, "isRwa": "false"} for symbol in self.symbols
                ]
            }
        return {"data": []}

    def _candles(self, symbol: str) -> list[Candle]:
        start = datetime(2022, 1, 1, tzinfo=UTC)
        price = 100.0 + (sum(ord(char) for char in symbol) % 17)
        candles: list[Candle] = []
        for day in range(self.days):
            for hour in range(0, 24, 4):
                moment = start + timedelta(days=day, hours=hour)
                drift = 0.002 + 0.0004 * math.sin(day / 9.0)
                open_price = price
                price = open_price * math.exp(drift)
                candles.append(
                    Candle(
                        symbol=symbol,
                        timeframe="4H",
                        timestamp_utc=moment,
                        open=Decimal(str(round(open_price, 8))),
                        high=Decimal(str(round(max(open_price, price) * 1.001, 8))),
                        low=Decimal(str(round(min(open_price, price) * 0.999, 8))),
                        close=Decimal(str(round(price, 8))),
                        volume=Decimal(1000),
                    )
                )
        return candles

    def fetch_candle_range(
        self, symbol: str, granularity: str, start_ms: int, end_ms: int
    ) -> list[Candle]:
        self.requests += 1
        return self._candles(symbol)

    def fetch_candles_batch(self, spec: list[tuple[str, str, int]]) -> dict:
        self.requests += 1
        output = {}
        for symbol, granularity, limit in spec:
            output[(symbol, granularity)] = self._candles(symbol)[-limit:]
        return output


def _config():
    return replace(
        default_config(),
        min_history=100,
        min_universe=4,
        target_vol=0.15,
        max_positions=3,
        cost_bps=10.0,
        funding_long_bps_day=0.0,
        funding_short_bps_day=0.0,
        regime_ma=100,
        regime_buffer=0.0,
        regime_mom_filter=0,
        max_drawdown_stop=0.0,
    )


def test_live_state_roundtrip() -> None:
    state = LiveState(
        equity_usdt=1_234.5,
        positions={
            "WLDUSDT": LivePosition(
                symbol="WLDUSDT",
                dollars=100.0,
                entry_price=2.0,
                entry_ts="2026-01-01T00:00:00+00:00",
                atr=0.1,
                weight=0.08,
            )
        },
        targets={"WLDUSDT": 0.08},
    )
    restored = LiveState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.equity_usdt == pytest.approx(1_234.5)
    assert restored.positions["WLDUSDT"].entry_price == pytest.approx(2.0)
    assert restored.targets["WLDUSDT"] == pytest.approx(0.08)


def test_snapshot_marks_unrealized_and_drawdown() -> None:
    state = LiveState(
        starting_equity_usdt=1_000.0,
        equity_usdt=900.0,
        peak_equity_usdt=1_000.0,
        positions={
            "WLDUSDT": LivePosition(
                symbol="WLDUSDT",
                dollars=200.0,
                entry_price=1.0,
                entry_ts="2026-01-01T00:00:00+00:00",
                atr=0.1,
                weight=0.2,
            )
        },
        last_prices={"WLDUSDT": 1.1},
    )
    snapshot = snapshot_state(state)
    assert snapshot["max_drawdown_pct"] == pytest.approx(10.0)
    assert snapshot["positions"][0]["unrealized_usdt"] == pytest.approx(20.0)


def test_live_trader_rebalances_once_per_day(tmp_path: Path) -> None:
    symbols = ["BTCUSDT"] + [f"SYM{index}USDT" for index in range(9)]
    client = FakeClient(symbols)
    trader = AlphaLiveTrader(
        _config(),
        client=client,
        state_path=tmp_path / "alpha_ledger.json",
        panel_dir=tmp_path / "panel" / "4h",
        starting_equity_usdt=1_000.0,
    )
    first = trader.step(now=datetime(2022, 12, 1, 6, 0, tzinfo=UTC))
    assert first["positions"], "the first daily cycle must open positions"
    first_costs = trader.state.costs_usdt
    first_positions = dict(trader.state.positions)
    assert first_costs > 0

    # Same UTC day: mark only, never rotate the book.
    second = trader.step(now=datetime(2022, 12, 1, 12, 0, tzinfo=UTC))
    assert trader.state.costs_usdt == pytest.approx(first_costs)
    assert {p["symbol"] for p in second["positions"]} == set(first_positions)
    assert trader.state.last_rebalance_day == "2022-12-01"

    # New day: a rebalance is allowed.
    trader.step(now=datetime(2022, 12, 2, 6, 0, tzinfo=UTC))
    assert trader.state.last_rebalance_day == "2022-12-02"


def test_force_rebalance_reenters_and_charges_fees(tmp_path: Path) -> None:
    symbols = ["BTCUSDT"] + [f"SYM{index}USDT" for index in range(9)]
    client = FakeClient(symbols)
    trader = AlphaLiveTrader(
        _config(),
        client=client,
        state_path=tmp_path / "alpha_ledger.json",
        panel_dir=tmp_path / "panel" / "4h",
        starting_equity_usdt=1_000.0,
    )
    trader.step(force_rebalance=True, now=datetime(2022, 12, 1, 6, 0, tzinfo=UTC))
    costs = trader.state.costs_usdt
    assert costs > 0
    trader.step(force_rebalance=True, now=datetime(2022, 12, 1, 7, 0, tzinfo=UTC))
    assert trader.state.costs_usdt >= costs
    assert trader.state.equity_usdt <= 1_000.0
