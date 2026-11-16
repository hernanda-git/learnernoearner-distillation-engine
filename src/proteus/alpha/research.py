"""Research driver: grid, walk-forward, and overfitting accounting.

`proteus.alpha.research` is the only place that chooses parameters. The
selection protocol is deliberately small and pre-registered:

* a fixed grid of 32 economically motivated configurations,
* expanding-window walk-forward: for each test year, the configuration with the
  best in-sample Sharpe is applied to the *next* year,
* aggregation of the stitched out-of-sample returns,
* deflated Sharpe and CSCV PBO across the full grid.

No configuration is chosen after looking at the test years.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from proteus.alpha.metrics import (
    block_bootstrap,
    deflated_sharpe,
    probability_of_backtest_overfitting,
    returns_of,
    summarize,
)
from proteus.alpha.panel import Panel, iso_day, parse_day
from proteus.alpha.portfolio import AlphaConfig
from proteus.alpha.signals import SeriesStats
from proteus.alpha.simulator import (
    SimulationResult,
    build_stats_cache,
    run_simulation,
)


def default_config() -> AlphaConfig:
    """Pre-registered core: absolute momentum, long-only, BTC regime gate.

    The family is fixed before the test years are read: an asset must trend up
    on its own (time-series momentum), the book is long-only because crypto
    short legs are squeeze-prone, and BTC must be above its 200-day average by
    2% with positive 60-day momentum before any long is admitted.
    """
    return AlphaConfig(
        name="core",
        signal_mode="ts",
        lookback_fast=14,
        lookback_slow=60,
        fast_weight=0.5,
        trend_ma=50,
        regime_ma=200,
        regime_buffer=0.02,
        regime_mom_filter=60,
        vol_window=30,
        atr_window=20,
        max_positions=8,
        min_universe=8,
        gross_target=1.0,
        target_vol=0.15,
        max_leverage=2.0,
        per_asset_cap=0.25,
        tilt_bull=0.5,
        tilt_bear=-1.0,
        allow_shorts=False,
        rebalance_days=7,
        min_history=365,
        min_dollar_volume=2_000_000.0,
        max_asset_vol=3.0,
        stop_atr=4.0,
        cost_bps=8.0,
        funding_long_bps_day=2.0,
        funding_short_bps_day=0.5,
        max_drawdown_stop=0.30,
        cooldown_days=20,
    )


def _label(config: AlphaConfig) -> str:
    return (
        f"ts{config.lookback_fast}-{config.lookback_slow}"
        f"_k{config.max_positions}"
        f"_v{round(config.target_vol * 100)}"
    )


def config_grid() -> list[AlphaConfig]:
    """16 pre-registered configurations; only lookback, breadth, and vol vary."""
    base = default_config()
    output: list[AlphaConfig] = []
    for fast, slow in ((7, 30), (14, 60), (30, 90), (14, 90)):
        for positions in (5, 8):
            for vol_target in (0.15, 0.20):
                config = replace(
                    base,
                    lookback_fast=fast,
                    lookback_slow=slow,
                    max_positions=positions,
                    target_vol=vol_target,
                )
                output.append(replace(config, name=_label(config)))
    return output


def run_config(
    panel: Panel,
    config: AlphaConfig,
    stats_by_symbol: dict[str, SeriesStats],
    *,
    start: int | None = None,
    end: int | None = None,
    initial_equity: float = 1_000_000.0,
) -> tuple[SimulationResult, dict[str, object]]:
    result = run_simulation(
        panel,
        stats_by_symbol,
        config,
        start_ts=start,
        end_ts=end,
        initial_equity=initial_equity,
    )
    metrics = summarize(
        result.equity,
        result.dates,
        initial_equity=initial_equity,
        costs_paid=result.costs_paid,
        funding_paid=result.funding_paid,
        trades=result.trades,
        rebalances=result.rebalances,
        gross_exposure=result.gross_exposure,
        net_exposure=result.net_exposure,
        turnover=result.daily_turnover,
    )
    return result, metrics


def _cache_for(panel: Panel, configs: list[AlphaConfig]) -> dict[tuple[object, ...], dict[str, SeriesStats]]:
    return build_stats_cache(panel, configs)


def run_grid(
    panel: Panel,
    configs: list[AlphaConfig],
    *,
    start: int,
    end: int,
) -> dict[str, dict[str, object]]:
    cache = _cache_for(panel, configs)
    output: dict[str, dict[str, object]] = {}
    for config in configs:
        result, metrics = run_config(
            panel, config, cache[config.stats_key()], start=start, end=end
        )
        output[config.name] = {
            "config": asdict(config),
            "metrics": metrics,
            "returns": returns_of(result.equity),
            "dates": result.dates[1:],
            "final_positions": result.final_positions,
            "costs_paid": result.costs_paid,
            "funding_paid": result.funding_paid,
            "trades": result.trades,
        }
    return output


def _year_bounds(start: int, end: int) -> list[tuple[int, int, int]]:
    """Return (train_start, test_start, test_end) for each test year."""
    first_year = datetime.fromtimestamp(start / 1000, tz=UTC).year
    last_year = datetime.fromtimestamp(end / 1000, tz=UTC).year
    bounds: list[tuple[int, int, int]] = []
    for year in range(first_year + 1, last_year + 1):
        test_start = parse_day(f"{year}-01-01")
        test_end = parse_day(f"{year}-12-31")
        test_end = min(test_end, end)
        if test_start <= start or test_start > end:
            continue
        bounds.append((start, test_start, test_end))
    return bounds


def walk_forward(
    panel: Panel,
    configs: list[AlphaConfig],
    *,
    start: int,
    end: int,
    min_train_days: int = 200,
) -> dict[str, object]:
    """Expanding-window walk-forward; returns stitched out-of-sample results."""
    cache = _cache_for(panel, configs)
    selections: list[dict[str, object]] = []
    stitched_dates: list[int] = []
    stitched_returns: list[float] = []
    stitched_equity: list[float] = [1.0]

    for train_start, test_start, test_end in _year_bounds(start, end):
        train_end = test_start - 86_400_000
        train_days = max(0, (train_end - train_start) // 86_400_000)
        if train_days < min_train_days:
            continue
        scored: list[tuple[float, AlphaConfig, dict[str, object]]] = []
        for config in configs:
            _, train_metrics = run_config(
                panel,
                config,
                cache[config.stats_key()],
                start=train_start,
                end=train_end,
            )
            sharpe = float(train_metrics.get("sharpe", 0.0) or 0.0)
            if (
                int(train_metrics.get("observations", 0) or 0) >= 180
                and int(train_metrics.get("trades", 0) or 0) >= 10
                and float(train_metrics.get("avg_gross", 0.0) or 0.0) > 0.01
            ):
                scored.append((sharpe, config, train_metrics))
        if not scored:
            continue
        scored.sort(key=lambda item: item[0], reverse=True)
        train_sharpe, chosen, train_metrics = scored[0]
        result, test_metrics = run_config(
            panel,
            chosen,
            cache[chosen.stats_key()],
            start=test_start,
            end=test_end,
        )
        year = datetime.fromtimestamp(test_start / 1000, tz=UTC).year
        selections.append(
            {
                "year": year,
                "config": chosen.name,
                "train_sharpe": round(train_sharpe, 3),
                "train_observations": train_metrics.get("observations"),
                "test_metrics": test_metrics,
                "test_dates": [iso_day(ts) for ts in result.dates[1:]],
            }
        )
        year_returns = returns_of(result.equity)
        stitched_returns.extend(year_returns)
        stitched_dates.extend(result.dates[1:])
        for value in year_returns:
            stitched_equity.append(stitched_equity[-1] * (1.0 + value))

    oos_metrics = summarize(
        stitched_equity,
        [stitched_dates[0] - 86_400_000, *stitched_dates] if stitched_dates else [0],
        initial_equity=1.0,
    )
    return {
        "selections": selections,
        "oos_metrics": oos_metrics,
        "stitched_equity": stitched_equity,
        "stitched_dates": stitched_dates,
        "stitched_returns": stitched_returns,
    }


def benchmark_buy_and_hold(
    panel: Panel,
    symbol: str,
    *,
    start: int,
    end: int,
) -> dict[str, object]:
    series = panel.series.get(symbol)
    if series is None:
        return {"symbol": symbol, "metrics": {"observations": 0}}
    bars = [bar for bar in series.bars if start <= bar.ts <= end]
    if len(bars) < 3:
        return {"symbol": symbol, "metrics": {"observations": 0}}
    equity = [bar.close / bars[0].open for bar in bars]
    metrics = summarize(equity, [bar.ts for bar in bars], initial_equity=1.0)
    return {"symbol": symbol, "metrics": metrics}


def research_report(
    panel: Panel,
    *,
    start: int,
    end: int,
    output_dir: Path | None = None,
) -> dict[str, object]:
    configs = config_grid()
    core = default_config()
    all_configs = [core, *configs]
    cache = _cache_for(panel, all_configs)

    core_result, core_metrics = run_config(
        panel, core, cache[core.stats_key()], start=start, end=end
    )
    grid = run_grid(panel, configs, start=start, end=end)
    trial_sharpes = [float(row["metrics"].get("sharpe", 0.0) or 0.0) for row in grid.values()]
    trial_sharpes.append(float(core_metrics.get("sharpe", 0.0) or 0.0))

    core_returns = returns_of(core_result.equity)
    core_dsr = deflated_sharpe(
        float(core_metrics.get("sharpe", 0.0) or 0.0),
        trials=len(all_configs),
        observations=int(core_metrics.get("observations", 0) or 0),
        skew=float(core_metrics.get("skew", 0.0) or 0.0),
        kurt=float(core_metrics.get("kurtosis", 0.0) or 0.0),
        trial_sharpes=trial_sharpes,
    )
    core_metrics["deflated_sharpe"] = round(core_dsr, 4)
    # The frozen core is one pre-registered choice; the grid is a search. Report
    # both so the search penalty is visible instead of hidden in one number.
    core_metrics["deflated_sharpe_preregistered"] = round(
        deflated_sharpe(
            float(core_metrics.get("sharpe", 0.0) or 0.0),
            trials=1,
            observations=int(core_metrics.get("observations", 0) or 0),
            skew=float(core_metrics.get("skew", 0.0) or 0.0),
            kurt=float(core_metrics.get("kurtosis", 0.0) or 0.0),
        ),
        4,
    )
    core_metrics["bootstrap"] = block_bootstrap(core_returns)

    # Align grid returns on a common timeline for PBO.
    common_dates = core_result.dates[1:]
    aligned: dict[str, list[float]] = {"core": core_returns}
    for name, row in grid.items():
        dates = row["dates"]
        mapping = dict(zip(dates, row["returns"], strict=False))
        aligned[name] = [float(mapping.get(ts, 0.0)) for ts in common_dates]
    pbo = probability_of_backtest_overfitting(aligned)

    holdout_start = parse_day("2024-01-01")
    _, holdout_metrics = run_config(
        panel, core, cache[core.stats_key()], start=holdout_start, end=end
    )
    walk = walk_forward(panel, all_configs, start=start, end=end)
    btc = benchmark_buy_and_hold(panel, "BTCUSDT", start=start, end=end)
    equal_weight = _equal_weight_benchmark(panel, start=start, end=end)

    report: dict[str, object] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "window": {"start": iso_day(start), "end": iso_day(end)},
        "universe": {
            "symbols": len(panel.series),
            "first_bar": iso_day(panel.calendar[0]) if panel.calendar else None,
            "last_bar": iso_day(panel.calendar[-1]) if panel.calendar else None,
        },
        "core": {"config": asdict(core), "metrics": core_metrics},
        "grid": {
            name: {"config": row["config"], "metrics": row["metrics"]}
            for name, row in grid.items()
        },
        "overfitting": {"pbo": pbo, "trials": len(all_configs)},
        "holdout_2024": {"start": "2024-01-01", "metrics": holdout_metrics},
        "walk_forward": walk,
        "benchmarks": {"btc_buy_and_hold": btc, "equal_weight": equal_weight},
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "alpha-research.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
        )
    return report


def _equal_weight_benchmark(panel: Panel, *, start: int, end: int) -> dict[str, object]:
    days = [ts for ts in panel.window(start, end)]
    if len(days) < 3:
        return {"metrics": {"observations": 0}}
    equity: list[float] = [1.0]
    for index in range(len(days) - 1):
        ts, nxt = days[index], days[index + 1]
        moves: list[float] = []
        for series in panel.series.values():
            current = series.by_ts.get(ts)
            following = series.by_ts.get(nxt)
            if current and following and current.close > 0:
                moves.append(following.open / current.open - 1.0)
        equity.append(equity[-1] * (1.0 + (sum(moves) / len(moves) if moves else 0.0)))
    return {"metrics": summarize(equity, days, initial_equity=1.0)}


__all__ = [
    "benchmark_buy_and_hold",
    "config_grid",
    "default_config",
    "research_report",
    "run_config",
    "run_grid",
    "walk_forward",
]
