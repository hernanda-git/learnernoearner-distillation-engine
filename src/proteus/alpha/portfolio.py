"""Cross-sectional target construction (`proteus.alpha.portfolio`).

The portfolio is built once per rebalance from completed daily closes:

1. **Universe filter** — enough history, a real next-day open, a dollar-volume
   floor, and a volatility ceiling.
2. **Risk-adjusted momentum score** — cross-sectional z-score of fast and slow
   total return divided by annualized volatility (a horizon Sharpe), blended by
   ``fast_weight``.
3. **Trend admission** — longs need ``close > trend_ma``; shorts need the
   mirror image.
4. **Inverse-volatility weights** within each side, capped per asset, with a
   regime-dependent net tilt.
5. **Volatility targeting** — scale the whole book toward ``target_vol`` while
   respecting ``max_leverage``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from proteus.alpha.panel import DAY_MS, iso_day
from proteus.alpha.signals import SeriesStats, cross_sectional_z


@dataclass(frozen=True, slots=True)
class AlphaConfig:
    """Pre-registered strategy configuration; every field is a documented choice."""

    name: str = "core"
    signal_mode: str = "xs"
    regime_buffer: float = 0.0
    regime_mom_filter: int = 0
    lookback_fast: int = 7
    lookback_slow: int = 30
    fast_weight: float = 0.5
    trend_ma: int = 50
    regime_ma: int = 100
    vol_window: int = 30
    atr_window: int = 20
    max_positions: int = 6
    min_universe: int = 8
    gross_target: float = 1.0
    target_vol: float = 0.20
    max_leverage: float = 2.0
    per_asset_cap: float = 0.25
    tilt_bull: float = 0.5
    tilt_bear: float = -0.2
    allow_shorts: bool = True
    rebalance_days: int = 7
    min_history: int = 120
    min_dollar_volume: float = 2_000_000.0
    max_asset_vol: float = 3.0
    min_score: float = 0.0
    stop_atr: float = 0.0
    cost_bps: float = 8.0
    funding_long_bps_day: float = 2.0
    funding_short_bps_day: float = 2.0
    max_drawdown_stop: float = 0.30
    cooldown_days: int = 20

    def stats_key(self) -> tuple[object, ...]:
        return (
            self.lookback_fast,
            self.lookback_slow,
            self.trend_ma,
            self.regime_ma,
            self.vol_window,
            self.atr_window,
        )


@dataclass(frozen=True, slots=True)
class Target:
    symbol: str
    weight: float
    score: float
    volatility: float
    atr: float


@dataclass(frozen=True, slots=True)
class TargetBook:
    targets: dict[str, Target]
    gross: float
    net: float
    ex_ante_vol: float
    regime_bull: bool
    eligible: int
    long_count: int
    short_count: int


def regime_is_bull(
    btc_stats: SeriesStats | None,
    ts: int,
    ma_window: int,
    *,
    buffer: float = 0.0,
    mom_filter: int = 0,
) -> bool:
    """BTC above its long moving average = risk-on. Missing history is risk-on.

    ``buffer`` requires BTC to clear the average by a margin, and ``mom_filter``
    additionally requires positive BTC momentum over that horizon. Both reduce
    the SMA whipsaw that re-entered longs during the 2022 bear rallies.
    """
    if btc_stats is None:
        return True
    index = btc_stats.index_of(ts)
    if index is None:
        return True
    sma = btc_stats.sma.get(ma_window, [])
    if index >= len(sma) or sma[index] is None:
        return True
    if btc_stats.close[index] <= float(sma[index]) * (1.0 + buffer):  # type: ignore[arg-type]
        return False
    if mom_filter > 0:
        moments = btc_stats.mom.get(mom_filter)
        if moments is None or index >= len(moments) or moments[index] is None:
            return True
        if float(moments[index]) <= 0:  # type: ignore[arg-type]
            return False
    return True


def _risk_adjusted_momentum(
    stats: SeriesStats, index: int, horizon: int, volatility: float
) -> float | None:
    moments = stats.mom.get(horizon)
    if moments is None or index >= len(moments) or moments[index] is None:
        return None
    scale = volatility * math.sqrt(horizon / 365.0)
    if scale <= 1e-12:
        return None
    return float(moments[index]) / scale  # type: ignore[arg-type]


def build_targets(
    stats_by_symbol: dict[str, SeriesStats],
    ts: int,
    config: AlphaConfig,
    *,
    require_next_bar: bool = True,
) -> TargetBook:
    """Build the target book from the close of ``ts``.

    ``require_next_bar`` is the backtest's execution guard: a symbol is only
    tradable when the next day's open exists. The live trader executes at the
    current price, so it disables the guard for the newest completed bar.
    """
    regime_bull = regime_is_bull(
        stats_by_symbol.get("BTCUSDT"),
        ts,
        config.regime_ma,
        buffer=config.regime_buffer,
        mom_filter=config.regime_mom_filter,
    )
    raw: dict[str, dict[str, float]] = {}
    for symbol, stats in stats_by_symbol.items():
        if symbol == "BTCUSDT":
            # BTC is the regime anchor, not a candidate: its own volatility
            # dominates the book and turns the strategy into beta.
            continue
        index = stats.index_of(ts)
        if index is None or index < config.min_history - 1:
            continue
        if require_next_bar and (
            index + 1 >= len(stats.ts) or stats.ts[index + 1] != ts + DAY_MS
        ):
            continue
        volatility = stats.vol[index]
        if volatility is None or not (0.0 < volatility <= config.max_asset_vol):
            continue
        atr = stats.atr[index]
        if atr is None or atr <= 0:
            continue
        if stats.dollar_volume[index] < config.min_dollar_volume:
            continue
        fast = _risk_adjusted_momentum(stats, index, config.lookback_fast, volatility)
        slow = _risk_adjusted_momentum(stats, index, config.lookback_slow, volatility)
        if fast is None or slow is None:
            continue
        trend = stats.sma.get(config.trend_ma, [])
        if index >= len(trend) or trend[index] is None:
            continue
        raw[symbol] = {
            "fast": fast,
            "slow": slow,
            "vol": volatility,
            "atr": atr,
            "close": stats.close[index],
            "trend": float(trend[index]),  # type: ignore[arg-type]
        }

    if len(raw) < config.min_universe:
        return TargetBook({}, 0.0, 0.0, 0.0, regime_bull, len(raw), 0, 0)

    fast_z = cross_sectional_z({symbol: row["fast"] for symbol, row in raw.items()})
    slow_z = cross_sectional_z({symbol: row["slow"] for symbol, row in raw.items()})
    if config.signal_mode == "ts":
        # Absolute (time-series) momentum: an asset must be trending up on its
        # own, not merely be the least-bad member of a falling cross-section.
        scores = {
            symbol: config.fast_weight * raw[symbol]["fast"]
            + (1.0 - config.fast_weight) * raw[symbol]["slow"]
            for symbol in raw
        }
    else:
        scores = {
            symbol: config.fast_weight * fast_z[symbol]
            + (1.0 - config.fast_weight) * slow_z[symbol]
            for symbol in raw
        }

    ranked = sorted(scores, key=lambda symbol: scores[symbol], reverse=True)
    longs = [
        symbol
        for symbol in ranked
        if scores[symbol] > config.min_score
        and raw[symbol]["close"] > raw[symbol]["trend"]
    ][: config.max_positions]
    shorts = (
        [
            symbol
            for symbol in reversed(ranked)
            if scores[symbol] < -config.min_score
            and raw[symbol]["close"] < raw[symbol]["trend"]
        ][: config.max_positions]
        if config.allow_shorts
        else []
    )

    if not longs and not shorts:
        return TargetBook(
            {}, 0.0, 0.0, 0.0, regime_bull, len(raw), 0, 0
        )

    net_tilt = config.tilt_bull if regime_bull else config.tilt_bear
    long_gross = config.gross_target * (1.0 + net_tilt) / 2.0
    short_gross = config.gross_target * (1.0 - net_tilt) / 2.0

    weights: dict[str, float] = {}

    def side_weights(selected: list[str], gross_side: float, sign: float) -> None:
        if not selected or gross_side <= 0:
            return
        inverse = {symbol: 1.0 / raw[symbol]["vol"] for symbol in selected}
        total = sum(inverse.values())
        if total <= 0:
            return
        assigned: dict[str, float] = {}
        for symbol, value in inverse.items():
            weight = sign * gross_side * value / total
            cap = config.per_asset_cap
            if abs(weight) > cap:
                weight = sign * cap
            assigned[symbol] = weight
        used = sum(abs(weight) for weight in assigned.values())
        if used > gross_side and used > 0:
            factor = gross_side / used
            assigned = {symbol: weight * factor for symbol, weight in assigned.items()}
        weights.update(assigned)

    side_weights(longs, long_gross, 1.0)
    side_weights(shorts, short_gross, -1.0)

    gross = sum(abs(weight) for weight in weights.values())
    net = sum(weights.values())
    ex_ante = math.sqrt(
        sum((weight * raw[symbol]["vol"]) ** 2 for symbol, weight in weights.items())
    )

    if ex_ante > 1e-9 and config.target_vol > 0:
        scale = config.target_vol / ex_ante
        if gross > 0:
            scale = min(scale, config.max_leverage / gross)
        scale = max(0.0, scale)
        weights = {symbol: weight * scale for symbol, weight in weights.items()}
        gross = sum(abs(weight) for weight in weights.values())
        net = sum(weights.values())

    if gross > config.max_leverage and gross > 0:
        factor = config.max_leverage / gross
        weights = {symbol: weight * factor for symbol, weight in weights.items()}
        gross *= factor
        net *= factor

    # The volatility scale is applied after the first cap, so re-apply the
    # per-asset cap to the final book.
    weights = {
        symbol: max(-config.per_asset_cap, min(config.per_asset_cap, weight))
        for symbol, weight in weights.items()
    }
    gross = sum(abs(weight) for weight in weights.values())
    net = sum(weights.values())

    targets = {
        symbol: Target(
            symbol=symbol,
            weight=weight,
            score=scores[symbol],
            volatility=raw[symbol]["vol"],
            atr=raw[symbol]["atr"],
        )
        for symbol, weight in weights.items()
        if abs(weight) > 1e-6
    }
    return TargetBook(
        targets=targets,
        gross=sum(abs(target.weight) for target in targets.values()),
        net=sum(target.weight for target in targets.values()),
        ex_ante_vol=ex_ante,
        regime_bull=regime_bull,
        eligible=len(raw),
        long_count=len(longs),
        short_count=len(shorts),
    )


__all__ = ["AlphaConfig", "Target", "TargetBook", "build_targets", "iso_day", "regime_is_bull"]
