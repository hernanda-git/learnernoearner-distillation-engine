"""Alpha research engine (`proteus.alpha`).

The distillation corpus answers *what the trader did*; this package answers
*what actually pays*. It is a cost-aware, walk-forward validated trend and
cross-sectional momentum portfolio built on multi-year Bitget 4H data:

* :mod:`proteus.alpha.panel` — 4H JSONL to completed UTC daily bars.
* :mod:`proteus.alpha.signals` — O(N) rolling volatility, ATR, SMA, momentum.
* :mod:`proteus.alpha.portfolio` — ranked targets, inverse-vol weights, regime
  tilt, volatility targeting.
* :mod:`proteus.alpha.simulator` — open-to-open accounting with fees, funding,
  stops, and a drawdown circuit breaker.
* :mod:`proteus.alpha.metrics` — drawdowns, deflated Sharpe, CSCV PBO, block
  bootstrap.
* :mod:`proteus.alpha.research` — grid, expanding walk-forward, benchmarks.
"""

from proteus.alpha.metrics import (
    annualized_sharpe,
    block_bootstrap,
    deflated_sharpe,
    max_drawdown,
    probability_of_backtest_overfitting,
    returns_of,
    summarize,
)
from proteus.alpha.panel import DailyBar, Panel, SymbolSeries, iso_day, parse_day
from proteus.alpha.portfolio import AlphaConfig, Target, TargetBook, build_targets
from proteus.alpha.research import (
    benchmark_buy_and_hold,
    config_grid,
    default_config,
    research_report,
    run_config,
    run_grid,
    walk_forward,
)
from proteus.alpha.signals import SeriesStats, compute_stats
from proteus.alpha.simulator import (
    SimulationResult,
    build_stats_cache,
    run_simulation,
)

__all__ = [
    "AlphaConfig",
    "DailyBar",
    "Panel",
    "SeriesStats",
    "SimulationResult",
    "SymbolSeries",
    "Target",
    "TargetBook",
    "annualized_sharpe",
    "benchmark_buy_and_hold",
    "block_bootstrap",
    "build_stats_cache",
    "build_targets",
    "compute_stats",
    "config_grid",
    "default_config",
    "deflated_sharpe",
    "iso_day",
    "max_drawdown",
    "parse_day",
    "probability_of_backtest_overfitting",
    "research_report",
    "returns_of",
    "run_config",
    "run_grid",
    "run_simulation",
    "summarize",
    "walk_forward",
]
