"""Performance and overfitting statistics (`proteus.alpha.metrics`).

Pure stdlib: normal CDF/quantile, drawdowns, deflated Sharpe ratio (Bailey &
Lopez de Prado), probability of backtest overfitting via CSCV, and a stationary
block bootstrap for Sharpe/CAGR confidence intervals.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Sequence
from datetime import UTC, datetime

TRADING_DAYS = 365.0
EULER_GAMMA = 0.5772156649015329


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def normal_ppf(probability: float) -> float:
    """Acklam's rational approximation; absolute error < 1.15e-9."""
    if probability <= 0.0:
        return -math.inf
    if probability >= 1.0:
        return math.inf
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    low = 0.02425
    high = 1.0 - low
    if probability < low:
        q = math.sqrt(-2.0 * math.log(probability))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if probability > high:
        q = math.sqrt(-2.0 * math.log(1.0 - probability))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    q = probability - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: Sequence[float], sample: bool = True) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / (n - 1 if sample else n)
    return math.sqrt(max(0.0, variance))


def skewness(values: Sequence[float]) -> float:
    n = len(values)
    if n < 3:
        return 0.0
    mean = _mean(values)
    std = _std(values, sample=False)
    if std <= 1e-12:
        return 0.0
    return sum(((value - mean) / std) ** 3 for value in values) / n


def kurtosis(values: Sequence[float]) -> float:
    """Excess kurtosis (Fisher)."""
    n = len(values)
    if n < 4:
        return 0.0
    mean = _mean(values)
    std = _std(values, sample=False)
    if std <= 1e-12:
        return 0.0
    return sum(((value - mean) / std) ** 4 for value in values) / n - 3.0


def max_drawdown(equity: Sequence[float]) -> tuple[float, int, int]:
    """Return (fractional drawdown, peak index, trough index)."""
    peak = equity[0] if equity else 1.0
    worst = 0.0
    peak_index = 0
    trough_index = 0
    current_peak_index = 0
    for index, value in enumerate(equity):
        if value > peak:
            peak = value
            current_peak_index = index
        if peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > worst:
                worst = drawdown
                peak_index = current_peak_index
                trough_index = index
    return worst, peak_index, trough_index


def yearly_returns(returns: Sequence[float], dates: Sequence[int]) -> dict[int, float]:
    buckets: dict[int, list[float]] = {}
    for value, ts in zip(returns, dates, strict=False):
        year = datetime.fromtimestamp(ts / 1000, tz=UTC).year
        buckets.setdefault(year, []).append(value)
    output: dict[int, float] = {}
    for year, values in buckets.items():
        compounded = 1.0
        for value in values:
            compounded *= 1.0 + value
        output[year] = compounded - 1.0
    return dict(sorted(output.items()))


def monthly_returns(returns: Sequence[float], dates: Sequence[int]) -> list[float]:
    buckets: dict[tuple[int, int], list[float]] = {}
    for value, ts in zip(returns, dates, strict=False):
        moment = datetime.fromtimestamp(ts / 1000, tz=UTC)
        buckets.setdefault((moment.year, moment.month), []).append(value)
    output: list[float] = []
    for key in sorted(buckets):
        compounded = 1.0
        for value in buckets[key]:
            compounded *= 1.0 + value
        output.append(compounded - 1.0)
    return output


def annualized_sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    std = _std(returns)
    return _mean(returns) / std * math.sqrt(TRADING_DAYS) if std > 1e-12 else 0.0


def summarize(
    equity: Sequence[float],
    dates: Sequence[int],
    *,
    initial_equity: float,
    costs_paid: float = 0.0,
    funding_paid: float = 0.0,
    trades: int = 0,
    rebalances: int = 0,
    gross_exposure: Sequence[float] = (),
    net_exposure: Sequence[float] = (),
    turnover: Sequence[float] = (),
) -> dict[str, float | int | dict[int, float]]:
    if len(equity) < 3 or len(returns_of(equity)) < 2:
        return {"observations": 0}
    returns = returns_of(equity)
    points = dates[1:]
    std = _std(returns)
    vol = std * math.sqrt(TRADING_DAYS)
    total_return = equity[-1] / initial_equity - 1.0
    days = max(1, (dates[-1] - dates[0]) / 86_400_000.0)
    cagr = (equity[-1] / initial_equity) ** (TRADING_DAYS / days) - 1.0
    downside = [min(value, 0.0) for value in returns]
    downside_std = math.sqrt(_mean([value * value for value in downside])) * math.sqrt(
        TRADING_DAYS
    )
    sharpe = _mean(returns) / std * math.sqrt(TRADING_DAYS) if std > 1e-12 else 0.0
    dd, peak_index, trough_index = max_drawdown(equity)
    calmar = cagr / dd if dd > 1e-12 else 0.0
    months = monthly_returns(returns, points)
    active = [value for value in returns if abs(value) > 1e-12]
    active_hit = (
        sum(1 for value in active if value > 0) / len(active) if active else 0.0
    )
    t_stat = (
        _mean(returns) / (std / math.sqrt(len(returns))) if std > 1e-12 else 0.0
    )
    return {
        "observations": len(returns),
        "start": datetime.fromtimestamp(dates[0] / 1000, tz=UTC).strftime("%Y-%m-%d"),
        "end": datetime.fromtimestamp(dates[-1] / 1000, tz=UTC).strftime("%Y-%m-%d"),
        "years": round(days / TRADING_DAYS, 2),
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "volatility": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "sortino": round(_mean(returns) / downside_std * math.sqrt(TRADING_DAYS), 4)
        if downside_std > 1e-12
        else 0.0,
        "max_drawdown": round(dd, 6),
        "calmar": round(calmar, 4),
        "hit_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4),
        "active_hit_rate": round(active_hit, 4),
        "active_share": round(len(active) / len(returns), 4),
        "skew": round(skewness(returns), 4),
        "kurtosis": round(kurtosis(returns), 4),
        "t_stat": round(t_stat, 3),
        "worst_day": round(min(returns), 6),
        "best_day": round(max(returns), 6),
        "positive_months": round(
            sum(1 for value in months if value > 0) / len(months), 4
        )
        if months
        else 0.0,
        "yearly": {year: round(value, 6) for year, value in yearly_returns(returns, points).items()},
        "cost_drag_pct": round(100.0 * costs_paid / initial_equity, 3),
        "funding_drag_pct": round(100.0 * funding_paid / initial_equity, 3),
        "trades": trades,
        "rebalances": rebalances,
        "avg_gross": round(_mean(list(gross_exposure)), 4) if gross_exposure else 0.0,
        "avg_net": round(_mean(list(net_exposure)), 4) if net_exposure else 0.0,
        "annual_turnover": round(
            sum(turnover) * TRADING_DAYS / max(1, len(turnover)), 3
        )
        if turnover
        else 0.0,
        "dd_peak_index": peak_index,
        "dd_trough_index": trough_index,
    }


def returns_of(equity: Sequence[float]) -> list[float]:
    return [
        equity[index] / equity[index - 1] - 1.0 if equity[index - 1] > 0 else 0.0
        for index in range(1, len(equity))
    ]


def deflated_sharpe(
    sharpe: float,
    *,
    trials: int,
    observations: int,
    skew: float = 0.0,
    kurt: float = 0.0,
    trial_sharpes: Sequence[float] | None = None,
) -> float:
    """Probability the observed Sharpe is real after ``trials`` attempts."""
    if observations < 3:
        return 0.0
    trial_variance = (
        _std(list(trial_sharpes), sample=True)
        if trial_sharpes and len(trial_sharpes) > 1
        else 1.0 / max(1, observations - 1)
    )
    if trials <= 1:
        benchmark = 0.0
    else:
        benchmark = math.sqrt(trial_variance) * (
            (1.0 - EULER_GAMMA) * normal_ppf(1.0 - 1.0 / trials)
            + EULER_GAMMA * normal_ppf(1.0 - 1.0 / (trials * math.e))
        )
    denominator = math.sqrt(
        max(1e-12, 1.0 - skew * sharpe + (kurt / 4.0) * sharpe * sharpe)
    )
    z = (sharpe - benchmark) * math.sqrt(max(1, observations - 1)) / denominator
    return normal_cdf(z)


def block_bootstrap(
    returns: Sequence[float],
    *,
    samples: int = 2_000,
    block_days: int = 20,
    seed: int = 7,
) -> dict[str, float]:
    """Stationary block bootstrap CI for Sharpe and CAGR."""
    if len(returns) < 30:
        return {}
    rng = random.Random(seed)
    count = len(returns)
    sharpes: list[float] = []
    cagrs: list[float] = []
    for _ in range(samples):
        path: list[float] = []
        while len(path) < count:
            start = rng.randrange(count)
            for offset in range(block_days):
                path.append(returns[(start + offset) % count])
                if len(path) >= count:
                    break
        sharpes.append(annualized_sharpe(path))
        final = 1.0
        for value in path:
            final *= 1.0 + value
        cagrs.append(final ** (TRADING_DAYS / count) - 1.0)
    sharpes.sort()
    cagrs.sort()

    def percentile(values: list[float], probability: float) -> float:
        return values[min(len(values) - 1, max(0, int(probability * len(values))))]

    return {
        "sharpe_p05": round(percentile(sharpes, 0.05), 3),
        "sharpe_p50": round(percentile(sharpes, 0.50), 3),
        "sharpe_p95": round(percentile(sharpes, 0.95), 3),
        "cagr_p05": round(percentile(cagrs, 0.05), 4),
        "cagr_p95": round(percentile(cagrs, 0.95), 4),
        "samples": samples,
    }


def probability_of_backtest_overfitting(
    returns_by_config: dict[str, Sequence[float]],
    *,
    splits: int = 10,
) -> dict[str, float]:
    """CSCV PBO (Bailey, Borwein, Lopez de Prado & Zhu).

    Splits the common timeline into ``splits`` contiguous blocks, uses every
    half-combination as in-sample, picks the best configuration there, and
    measures its out-of-sample rank. PBO is the share of combinations where the
    in-sample winner lands below the out-of-sample median.
    """
    names = list(returns_by_config)
    if len(names) < 2:
        return {"pbo": 0.0, "combinations": 0}
    length = min(len(returns_by_config[name]) for name in names)
    if length < splits * 4:
        return {"pbo": 0.0, "combinations": 0}
    blocks = [list(range(index * length // splits, (index + 1) * length // splits)) for index in range(splits)]
    half = splits // 2
    combinations = 0
    failures = 0
    for chosen in itertools.combinations(range(splits), half):
        in_sample_indices = [index for block in chosen for index in blocks[block]]
        out_sample_indices = [
            index
            for block in range(splits)
            if block not in chosen
            for index in blocks[block]
        ]
        if not in_sample_indices or not out_sample_indices:
            continue
        in_sample = {
            name: [returns_by_config[name][index] for index in in_sample_indices]
            for name in names
        }
        out_sample = {
            name: [returns_by_config[name][index] for index in out_sample_indices]
            for name in names
        }
        best = max(names, key=lambda name: annualized_sharpe(in_sample[name]))
        oos = {name: annualized_sharpe(out_sample[name]) for name in names}
        rank = sum(1 for name in names if oos[name] <= oos[best]) / len(names)
        combinations += 1
        if rank <= 0.5:
            failures += 1
    return {
        "pbo": round(failures / combinations, 3) if combinations else 1.0,
        "combinations": combinations,
    }


__all__ = [
    "annualized_sharpe",
    "block_bootstrap",
    "deflated_sharpe",
    "kurtosis",
    "max_drawdown",
    "normal_cdf",
    "normal_ppf",
    "probability_of_backtest_overfitting",
    "returns_of",
    "skewness",
    "summarize",
    "yearly_returns",
]
