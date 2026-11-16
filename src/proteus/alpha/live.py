"""Live paper portfolio for the alpha engine (`proteus.alpha.live`).

The distillation daemon rotates a three-slot book on every 15-minute candle
close; that structure is a fee engine, not a strategy. This module replaces it
with the validated portfolio process:

* a broad, volume-ranked universe refreshed daily,
* one decision per UTC day (after the daily close), not per candle,
* positions carried until the next rebalance, a stop, or the drawdown breaker,
* explicit fees and funding on the same schedule as the backtest.

State is a single JSON ledger plus an append-only closed-trade log. Nothing is
computed from the distillation corpus at runtime.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from proteus.alpha.panel import Panel
from proteus.alpha.portfolio import AlphaConfig, build_targets
from proteus.alpha.signals import SeriesStats, compute_stats

LIVE_GAP_DAYS = 400
LIVE_REBALANCE_MINUTE = 5
NON_CRYPTO_BASE = {
    "USDC", "USDT", "FDUSD", "TUSD", "DAI", "USDE", "EUR", "GBP", "JPY",
    "BRL", "TRY", "AUD", "CAD", "CHF", "CNH", "HKD", "IDR", "INR", "KRW",
    "MXN", "NGN", "NZD", "PHP", "PLN", "RUB", "SEK", "SGD", "THB", "UAH",
    "VND", "ZAR",
}


@dataclass
class LivePosition:
    symbol: str
    dollars: float
    entry_price: float
    entry_ts: str
    atr: float
    weight: float


@dataclass
class LiveState:
    starting_equity_usdt: float = 1_000.0
    equity_usdt: float = 1_000.0
    peak_equity_usdt: float = 1_000.0
    positions: dict[str, LivePosition] = field(default_factory=dict)
    last_prices: dict[str, float] = field(default_factory=dict)
    last_rebalance_day: str = ""
    last_funding_day: str = ""
    risk_off_until: str = ""
    costs_usdt: float = 0.0
    funding_usdt: float = 0.0
    closed_trades: list[dict[str, Any]] = field(default_factory=list)
    targets: dict[str, float] = field(default_factory=dict)
    regime_bull: bool = True
    gross: float = 0.0
    net: float = 0.0
    updated_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **{key: value for key, value in asdict(self).items() if key != "positions"},
            "positions": {
                symbol: asdict(position) for symbol, position in self.positions.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LiveState:
        positions = {
            symbol: LivePosition(**value)
            for symbol, value in (raw.get("positions") or {}).items()
        }
        return cls(
            starting_equity_usdt=float(raw.get("starting_equity_usdt", 1_000.0)),
            equity_usdt=float(raw.get("equity_usdt", 1_000.0)),
            peak_equity_usdt=float(raw.get("peak_equity_usdt", 1_000.0)),
            positions=positions,
            last_prices={key: float(value) for key, value in (raw.get("last_prices") or {}).items()},
            last_rebalance_day=str(raw.get("last_rebalance_day", "")),
            last_funding_day=str(raw.get("last_funding_day", "")),
            risk_off_until=str(raw.get("risk_off_until", "")),
            costs_usdt=float(raw.get("costs_usdt", 0.0)),
            funding_usdt=float(raw.get("funding_usdt", 0.0)),
            closed_trades=list(raw.get("closed_trades") or []),
            targets={key: float(value) for key, value in (raw.get("targets") or {}).items()},
            regime_bull=bool(raw.get("regime_bull", True)),
            gross=float(raw.get("gross", 0.0)),
            net=float(raw.get("net", 0.0)),
            updated_at_utc=str(raw.get("updated_at_utc", "")),
        )


def select_live_universe(client: Any, *, top: int = 120) -> list[str]:
    """Volume-ranked USDT perpetuals plus the trader's empirical universe."""
    from proteus.market import TRADABLE_UNIVERSE

    selected: list[str] = []
    try:
        payload = client.get_json("/api/v2/mix/market/tickers?productType=USDT-FUTURES")
        contracts = client.get_json("/api/v2/mix/market/contracts?productType=USDT-FUTURES")
        rwa = {
            row.get("symbol", "")
            for row in (contracts.get("data") or [])
            if str(row.get("isRwa", "false")).lower() == "true"
        }
        ranked: list[tuple[str, float]] = []
        for row in payload.get("data") or []:
            symbol = str(row.get("symbol", ""))
            if not symbol.endswith("USDT") or symbol in rwa:
                continue
            base = symbol.removesuffix("USDT")
            if base in NON_CRYPTO_BASE:
                continue
            try:
                volume = float(row.get("usdtVolume") or 0.0)
            except (TypeError, ValueError):
                continue
            if volume <= 0:
                continue
            ranked.append((symbol, volume))
        ranked.sort(key=lambda item: item[1], reverse=True)
        selected = [symbol for symbol, _ in ranked[:top]]
    except Exception:  # noqa: BLE001 - ticker discovery must fall back to the static universe
        selected = []

    for base in TRADABLE_UNIVERSE:
        symbol = f"{base.upper()}USDT"
        if symbol not in selected:
            selected.append(symbol)
    for required in ("BTCUSDT", "ETHUSDT"):
        if required not in selected:
            selected.insert(0, required)
    return selected


class LivePanelStore:
    """Per-symbol 4H JSONL cache that survives restarts."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, symbol: str) -> Path:
        return self.directory / f"{symbol}.jsonl"

    @staticmethod
    def _candle_row(candle: Any) -> dict[str, float]:
        return {
            "ts": int(candle.timestamp_utc.timestamp() * 1000),
            "o": float(candle.open),
            "h": float(candle.high),
            "l": float(candle.low),
            "c": float(candle.close),
            "v": float(candle.volume),
        }

    def _read(self, symbol: str) -> dict[int, dict[str, float]]:
        path = self.path(symbol)
        rows: dict[int, dict[str, float]] = {}
        if not path.exists():
            return rows
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[int(row["ts"])] = row
        return rows

    def _write(self, symbol: str, rows: dict[int, dict[str, float]]) -> None:
        path = self.path(symbol)
        temp = path.with_suffix(".jsonl.tmp")
        temp.write_text(
            "\n".join(
                json.dumps(rows[ts], separators=(",", ":")) for ts in sorted(rows)
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)

    def backfill(
        self, client: Any, symbols: Iterable[str], *, start_ms: int
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for symbol in symbols:
            if self.path(symbol).exists():
                continue
            try:
                candles = client.fetch_candle_range(
                    symbol, "4H", start_ms, int(datetime.now(UTC).timestamp() * 1000)
                )
            except Exception:  # noqa: BLE001 - one bad symbol must not stop the backfill
                candles = []
            rows = {int(candle.timestamp_utc.timestamp() * 1000): self._candle_row(candle) for candle in candles}
            if rows:
                self._write(symbol, rows)
            counts[symbol] = len(rows)
        return counts

    def update(self, client: Any, symbols: Iterable[str]) -> None:
        symbols = list(symbols)
        if not symbols:
            return
        spec = [(symbol, "4H", 18) for symbol in symbols]
        fetched = client.fetch_candles_batch(spec)
        for symbol in symbols:
            candles = fetched.get((symbol, "4H")) or []
            if not candles:
                continue
            rows = self._read(symbol)
            for candle in candles:
                row = self._candle_row(candle)
                rows[int(row["ts"])] = row
            self._write(symbol, rows)

    def last_prices(self) -> dict[str, float]:
        prices: dict[str, float] = {}
        for path in self.directory.glob("*.jsonl"):
            rows = self._read(path.stem)
            if rows:
                prices[path.stem] = float(rows[max(rows)]["c"])
        return prices

    def panel(self) -> Panel:
        return Panel.load(self.directory, drop_partial_last_day=True)


class AlphaLiveTrader:
    """Daily-rebalanced paper portfolio driven by :class:`AlphaConfig`."""

    def __init__(
        self,
        config: AlphaConfig,
        *,
        client: Any,
        state_path: Path,
        panel_dir: Path,
        starting_equity_usdt: float = 1_000.0,
        universe_top: int = 120,
    ) -> None:
        self.config = config
        self.client = client
        self.state_path = Path(state_path)
        self.store = LivePanelStore(panel_dir)
        self.starting_equity_usdt = starting_equity_usdt
        self.universe_top = universe_top
        self.state = self._load()
        self.universe: list[str] = []

    # ------------------------------------------------------------------ state
    def _load(self) -> LiveState:
        if self.state_path.exists():
            try:
                return LiveState.from_dict(json.loads(self.state_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return LiveState(
            starting_equity_usdt=self.starting_equity_usdt,
            equity_usdt=self.starting_equity_usdt,
            peak_equity_usdt=self.starting_equity_usdt,
        )

    def _save(self) -> None:
        self.state.updated_at_utc = datetime.now(UTC).isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.state.to_dict(), indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.state_path)

    def _closed_log(self) -> Path:
        return self.state_path.with_name("alpha_closed_trades.jsonl")

    def _append_closed(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        path = self._closed_log()
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    # ------------------------------------------------------------ accounting
    def mark(self, prices: dict[str, float], now: datetime) -> None:
        for symbol, position in self.state.positions.items():
            price = prices.get(symbol)
            previous = self.state.last_prices.get(symbol)
            if price is None:
                continue
            if previous and previous > 0:
                self.state.equity_usdt += position.dollars * (price / previous - 1.0)
            self.state.last_prices[symbol] = price

        day = now.date().isoformat()
        if day != self.state.last_funding_day:
            gross_long = sum(p.dollars for p in self.state.positions.values() if p.dollars > 0)
            gross_short = -sum(p.dollars for p in self.state.positions.values() if p.dollars < 0)
            funding = (
                gross_long * self.config.funding_long_bps_day / 10_000.0
                + gross_short * self.config.funding_short_bps_day / 10_000.0
            )
            self.state.equity_usdt -= funding
            self.state.funding_usdt += funding
            self.state.last_funding_day = day

        self.state.peak_equity_usdt = max(
            self.state.peak_equity_usdt, self.state.equity_usdt
        )

    def _rebalance(
        self,
        targets: dict[str, float],
        prices: dict[str, float],
        atr_by_symbol: dict[str, float],
        now: datetime,
    ) -> None:
        target_dollars: dict[str, float] = {}
        for symbol, weight in targets.items():
            if symbol in prices and prices[symbol] > 0:
                target_dollars[symbol] = weight * self.state.equity_usdt

        closed: list[dict[str, Any]] = []
        traded = 0.0
        new_positions: dict[str, LivePosition] = {}
        for symbol in set(self.state.positions) | set(target_dollars):
            current = self.state.positions.get(symbol)
            current_dollars = current.dollars if current else 0.0
            target = target_dollars.get(symbol, 0.0)
            delta = target - current_dollars
            traded += abs(delta)
            price = prices.get(symbol, 0.0)
            if abs(target) < 1e-9:
                if current is not None and current.entry_price > 0 and price > 0:
                    pnl = current.dollars * (price / current.entry_price - 1.0)
                    closed.append(
                        {
                            "symbol": symbol,
                            "entry_ts": current.entry_ts,
                            "exit_ts": now.isoformat(),
                            "entry_price": current.entry_price,
                            "exit_price": price,
                            "dollars": current.dollars,
                            "pnl_usdt": round(pnl, 4),
                            "reason": "rebalance",
                        }
                    )
                continue
            if current is not None and (delta == 0 or (delta > 0) == (current.dollars > 0)):
                new_positions[symbol] = LivePosition(
                    symbol=symbol,
                    dollars=target,
                    entry_price=current.entry_price,
                    entry_ts=current.entry_ts,
                    atr=current.atr,
                    weight=targets.get(symbol, current.weight),
                )
            else:
                new_positions[symbol] = LivePosition(
                    symbol=symbol,
                    dollars=target,
                    entry_price=price,
                    entry_ts=now.isoformat(),
                    atr=atr_by_symbol.get(symbol, 0.0),
                    weight=targets.get(symbol, 0.0),
                )

        cost = traded * self.config.cost_bps / 10_000.0
        self.state.equity_usdt -= cost
        self.state.costs_usdt += cost
        self.state.positions = new_positions
        for symbol, price in prices.items():
            if symbol in target_dollars:
                self.state.last_prices[symbol] = price
        self.state.closed_trades.extend(closed)
        if len(self.state.closed_trades) > 500:
            self.state.closed_trades = self.state.closed_trades[-500:]
        self._append_closed(closed)
        self.state.targets = dict(targets)
        self.state.last_rebalance_day = now.date().isoformat()

    # ------------------------------------------------------------------ cycle
    def _stats(self, panel: Panel) -> dict[str, SeriesStats]:
        ma = tuple(sorted({20, 50, 100, 200, self.config.trend_ma, self.config.regime_ma}))
        lookbacks = tuple(
            sorted({7, 14, 30, 60, 90, 180, self.config.lookback_fast, self.config.lookback_slow})
        )
        return {
            symbol: compute_stats(
                series,
                lookbacks=lookbacks,
                ma_windows=ma,
                vol_window=self.config.vol_window,
                atr_window=self.config.atr_window,
            )
            for symbol, series in panel.series.items()
        }

    def step(self, *, force_rebalance: bool = False, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        if not self.universe:
            self.universe = select_live_universe(self.client, top=self.universe_top)
            start_ms = int((now - timedelta(days=LIVE_GAP_DAYS)).timestamp() * 1000)
            self.store.backfill(self.client, self.universe, start_ms=start_ms)

        day = now.date().isoformat()
        rebalance_due = force_rebalance or (
            day != self.state.last_rebalance_day
            and (now.hour > 0 or (now.hour == 0 and now.minute >= LIVE_REBALANCE_MINUTE))
        )

        if rebalance_due and day <= self.state.risk_off_until:
            rebalance_due = False

        if rebalance_due:
            self.store.update(self.client, self.universe)
            panel = self.store.panel()
            prices = self.store.last_prices()
            self.mark(prices, now)

            if (
                self.config.max_drawdown_stop > 0
                and self.state.equity_usdt
                < self.state.peak_equity_usdt * (1.0 - self.config.max_drawdown_stop)
            ):
                self.state.risk_off_until = (
                    now.date() + timedelta(days=self.config.cooldown_days)
                ).isoformat()
                self._rebalance({}, prices, {}, now)
                self._save()
                return self.snapshot()

            stats = self._stats(panel)
            last_completed = panel.calendar[-1] if panel.calendar else None
            book = (
                build_targets(stats, last_completed, self.config, require_next_bar=False)
                if last_completed
                else None
            )
            targets = (
                {symbol: target.weight for symbol, target in book.targets.items()}
                if book
                else {}
            )
            atr_by_symbol = (
                {symbol: target.atr for symbol, target in book.targets.items()}
                if book
                else {}
            )

            if self.config.stop_atr > 0:
                for symbol in list(targets):
                    position = self.state.positions.get(symbol)
                    price = prices.get(symbol)
                    if position is None or price is None or position.atr <= 0:
                        continue
                    stop = (
                        position.entry_price - self.config.stop_atr * position.atr
                        if position.dollars > 0
                        else position.entry_price + self.config.stop_atr * position.atr
                    )
                    if (position.dollars > 0 and price <= stop) or (
                        position.dollars < 0 and price >= stop
                    ):
                        targets.pop(symbol, None)

            self._rebalance(targets, prices, atr_by_symbol, now)
            self.state.regime_bull = bool(book.regime_bull) if book else self.state.regime_bull
            self.state.gross = float(book.gross) if book else 0.0
            self.state.net = float(book.net) if book else 0.0
        else:
            open_symbols = list(self.state.positions)
            if open_symbols:
                self.store.update(self.client, open_symbols)
            self.mark(self.store.last_prices(), now)

        self._save()
        return self.snapshot()

    # ---------------------------------------------------------------- reports
    def snapshot(self) -> dict[str, Any]:
        return snapshot_state(
            self.state, config_name=self.config.name, universe=len(self.universe)
        )


def snapshot_state(
    state: LiveState, *, config_name: str = "core", universe: int = 0
) -> dict[str, Any]:
    """Serialize a ledger into the API/UI shape without touching the network."""
    equity = state.equity_usdt
    peak = max(state.peak_equity_usdt, equity, 1e-9)
    positions = []
    for symbol, position in sorted(state.positions.items()):
        price = state.last_prices.get(symbol, position.entry_price)
        pnl = (
            position.dollars * (price / position.entry_price - 1.0)
            if position.entry_price > 0
            else 0.0
        )
        positions.append(
            {
                "symbol": symbol,
                "direction": "LONG" if position.dollars > 0 else "SHORT",
                "weight": round(position.dollars / max(equity, 1e-9), 4),
                "dollars": round(position.dollars, 2),
                "entry_price": position.entry_price,
                "last_price": price,
                "unrealized_usdt": round(pnl, 2),
                "entry_ts": position.entry_ts,
            }
        )
    return {
        "strategy": "alpha",
        "config": config_name,
        "starting_equity_usdt": state.starting_equity_usdt,
        "equity_usdt": round(equity, 2),
        "return_pct": round(
            (equity / state.starting_equity_usdt - 1.0) * 100.0, 2
        ),
        "peak_equity_usdt": round(peak, 2),
        "max_drawdown_pct": round((peak - equity) / peak * 100.0, 2),
        "costs_usdt": round(state.costs_usdt, 2),
        "funding_usdt": round(state.funding_usdt, 2),
        "positions": positions,
        "targets": [
            {"symbol": symbol, "weight": round(weight, 4)}
            for symbol, weight in sorted(state.targets.items())
        ],
        "regime_bull": state.regime_bull,
        "gross": round(state.gross, 3),
        "net": round(state.net, 3),
        "risk_off_until": state.risk_off_until,
        "last_rebalance_day": state.last_rebalance_day,
        "closed_trades": len(state.closed_trades),
        "updated_at_utc": state.updated_at_utc,
        "universe": universe,
    }


__all__ = [
    "AlphaLiveTrader",
    "LivePanelStore",
    "LivePosition",
    "LiveState",
    "select_live_universe",
    "snapshot_state",
]
