"""Portfolio simulator for the alpha engine (`proteus.alpha.simulator`).

Accounting is **open-to-open**: a target computed from the close of day ``d``
executes at the open of ``d + 1`` and earns the return from that open to the
next open. This avoids intrabar assumptions and guarantees no signal can see a
price it could not have traded.

Costs are explicit: ``cost_bps`` per side on traded notional, plus a daily
funding charge on gross long and short notional. Stops are evaluated on close
and executed at the next open, matching a once-a-day operator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from proteus.alpha.panel import DAY_MS, Panel, iso_day
from proteus.alpha.portfolio import AlphaConfig, build_targets
from proteus.alpha.signals import SeriesStats, compute_stats

BPS = 10_000.0


@dataclass
class SimulationResult:
    config: AlphaConfig
    dates: list[int] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)
    gross_exposure: list[float] = field(default_factory=list)
    net_exposure: list[float] = field(default_factory=list)
    daily_turnover: list[float] = field(default_factory=list)
    costs_paid: float = 0.0
    funding_paid: float = 0.0
    trades: int = 0
    rebalances: int = 0
    stop_exits: int = 0
    start_equity: float = 1.0
    final_positions: dict[str, float] = field(default_factory=dict)
    average_eligible: float = 0.0
    bull_share: float = 0.0
    diagnostics: dict[str, object] = field(default_factory=dict)

    def returns(self) -> list[float]:
        output: list[float] = []
        for index in range(1, len(self.equity)):
            previous = self.equity[index - 1]
            output.append(self.equity[index] / previous - 1.0 if previous > 0 else 0.0)
        return output

    def start_iso(self) -> str:
        return iso_day(self.dates[0]) if self.dates else ""

    def end_iso(self) -> str:
        return iso_day(self.dates[-1]) if self.dates else ""


def build_stats_cache(
    panel: Panel, configs: list[AlphaConfig]
) -> dict[tuple[object, ...], dict[str, SeriesStats]]:
    """Compute rolling stats once per distinct window set."""
    cache: dict[tuple[object, ...], dict[str, SeriesStats]] = {}
    for config in configs:
        key = config.stats_key()
        if key in cache:
            continue
        ma_windows = tuple(
            sorted({20, 50, 100, 200, config.trend_ma, config.regime_ma})
        )
        lookbacks = tuple(sorted({7, 14, 30, 60, 90, 180, config.lookback_fast, config.lookback_slow}))
        cache[key] = {
            symbol: compute_stats(
                series,
                lookbacks=lookbacks,
                ma_windows=ma_windows,
                vol_window=config.vol_window,
                atr_window=config.atr_window,
            )
            for symbol, series in panel.series.items()
        }
    return cache


def run_simulation(
    panel: Panel,
    stats_by_symbol: dict[str, SeriesStats],
    config: AlphaConfig,
    *,
    start_ts: int | None = None,
    end_ts: int | None = None,
    initial_equity: float = 1_000_000.0,
) -> SimulationResult:
    days = panel.window(start_ts, end_ts)
    result = SimulationResult(config=config, start_equity=initial_equity)
    if len(days) < 3:
        return result

    equity = float(initial_equity)
    peak = equity
    positions: dict[str, float] = {}
    entry_price: dict[str, float] = {}
    entry_atr: dict[str, float] = {}
    pending: dict[str, float] | None = None
    flatten = False
    risk_off_until = -1
    cost_rate = config.cost_bps / BPS
    funding_long = config.funding_long_bps_day / BPS
    funding_short = config.funding_short_bps_day / BPS

    result.dates.append(days[0])
    result.equity.append(equity)

    eligible_total = 0
    bull_days = 0

    for index in range(len(days) - 1):
        ts = days[index]
        nxt = days[index + 1]
        traded_today = 0.0

        # 1. Execute the target computed at the previous close, at today's open.
        if pending is not None or flatten:
            target_weights = {} if flatten else (pending or {})
            target_dollars: dict[str, float] = {}
            for symbol, weight in target_weights.items():
                stats = stats_by_symbol.get(symbol)
                if stats is None:
                    continue
                position_index = stats.index_of(ts)
                if position_index is None:
                    continue
                target_dollars[symbol] = weight * equity

            symbols = set(positions) | set(target_dollars)
            traded = 0.0
            new_positions: dict[str, float] = {}
            for symbol in symbols:
                current = positions.get(symbol, 0.0)
                target = target_dollars.get(symbol, 0.0)
                delta = target - current
                if abs(delta) < 1e-9:
                    if abs(target) >= 1e-9:
                        new_positions[symbol] = target
                    continue
                traded += abs(delta)
                result.trades += 1
                new_positions[symbol] = target
                stats = stats_by_symbol.get(symbol)
                position_index = stats.index_of(ts) if stats else None
                open_price = (
                    stats.open[position_index]
                    if stats is not None and position_index is not None
                    else None
                )
                if target == 0.0 or current == 0.0 or (target > 0) != (current > 0):
                    if open_price and open_price > 0:
                        entry_price[symbol] = open_price
                        atr_index = position_index
                        atr = (
                            stats.atr[atr_index]
                            if stats is not None and atr_index is not None
                            else None
                        )
                        entry_atr[symbol] = float(atr) if atr else 0.0
                    else:
                        entry_price.pop(symbol, None)
                        entry_atr.pop(symbol, None)
            for symbol in list(entry_price):
                if symbol not in new_positions:
                    entry_price.pop(symbol, None)
                    entry_atr.pop(symbol, None)
            cost = traded * cost_rate
            equity -= cost
            result.costs_paid += cost
            traded_today = traded
            positions = new_positions
            pending = None
            flatten = False

        # 2. Mark to the next open (the position was entered at today's open).
        pnl = 0.0
        for symbol, dollars in positions.items():
            stats = stats_by_symbol.get(symbol)
            if stats is None:
                continue
            current_index = stats.index_of(ts)
            next_index = stats.index_of(nxt)
            if current_index is None or next_index is None:
                continue
            open_now = stats.open[current_index]
            open_next = stats.open[next_index]
            if open_now > 0:
                pnl += dollars * (open_next / open_now - 1.0)
        equity += pnl

        # 3. Funding on gross notional, charged once per day.
        gross_long = sum(value for value in positions.values() if value > 0)
        gross_short = -sum(value for value in positions.values() if value < 0)
        funding = gross_long * funding_long + gross_short * funding_short
        equity -= funding
        result.funding_paid += funding

        peak = max(peak, equity)
        result.dates.append(nxt)
        result.equity.append(equity)
        gross = (gross_long + gross_short) / max(equity, 1e-9)
        result.gross_exposure.append(gross)
        result.net_exposure.append((gross_long - gross_short) / max(equity, 1e-9))
        result.daily_turnover.append(traded_today / max(equity, 1e-9))

        # 4. Close-of-day risk checks and scheduling.
        if (
            config.max_drawdown_stop > 0
            and equity < peak * (1.0 - config.max_drawdown_stop)
            and risk_off_until < index
        ):
            risk_off_until = index + config.cooldown_days
            flatten = True
            pending = None

        # Anchor the rebalance calendar to the epoch so a full run and a
        # single-year run hold the book on exactly the same days.
        rebalance_due = (
            index >= risk_off_until
            and (ts // DAY_MS) % max(1, config.rebalance_days) == 0
        )
        if rebalance_due:
            book = build_targets(stats_by_symbol, ts, config)
            eligible_total += book.eligible
            bull_days += 1 if book.regime_bull else 0
            pending = {symbol: target.weight for symbol, target in book.targets.items()}
            result.rebalances += 1

        if config.stop_atr > 0:
            exits: list[str] = []
            for symbol, dollars in positions.items():
                if dollars == 0 or symbol not in entry_price:
                    continue
                stats = stats_by_symbol.get(symbol)
                if stats is None:
                    continue
                position_index = stats.index_of(ts)
                if position_index is None:
                    continue
                close = stats.close[position_index]
                atr = entry_atr.get(symbol, 0.0)
                if atr <= 0:
                    continue
                stop_distance = config.stop_atr * atr
                if dollars > 0 and close <= entry_price[symbol] - stop_distance or dollars < 0 and close >= entry_price[symbol] + stop_distance:
                    exits.append(symbol)
            if exits:
                if pending is None:
                    pending = {}
                for symbol in exits:
                    pending[symbol] = 0.0
                    result.stop_exits += 1

    result.final_positions = {
        symbol: value for symbol, value in positions.items() if abs(value) > 1e-9
    }
    if result.rebalances:
        result.average_eligible = eligible_total / result.rebalances
        result.bull_share = bull_days / result.rebalances
    result.diagnostics = {
        "bars": len(result.dates),
        "days": max(1, (result.dates[-1] - result.dates[0]) // DAY_MS),
        "rebalances": result.rebalances,
        "trades": result.trades,
        "stop_exits": result.stop_exits,
        "costs_pct": 100.0 * result.costs_paid / initial_equity,
        "funding_pct": 100.0 * result.funding_paid / initial_equity,
        "average_eligible": round(result.average_eligible, 1),
        "bull_share": round(result.bull_share, 3),
    }
    return result


__all__ = ["SimulationResult", "build_stats_cache", "run_simulation"]
