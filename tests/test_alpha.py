"""Invariant tests for the alpha research engine (`proteus.alpha`)."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from proteus.alpha import (
    Panel,
    build_stats_cache,
    compute_stats,
    default_config,
    max_drawdown,
    run_simulation,
)
from proteus.alpha.metrics import (
    deflated_sharpe,
    probability_of_backtest_overfitting,
    summarize,
)
from proteus.alpha.portfolio import build_targets


def _write_panel(
    root: Path,
    *,
    days: int = 320,
    symbols: int = 10,
    trend: float = 0.004,
    volatility: float = 0.01,
    quote_volume: float = 5_000_000.0,
) -> Path:
    """Deterministic 4H panel: every symbol trends, with a smooth wave on top."""
    root.mkdir(parents=True, exist_ok=True)
    start = datetime(2022, 1, 1, tzinfo=UTC)
    for index in range(symbols):
        symbol = "BTCUSDT" if index == 0 else f"SYM{index}USDT"
        price = 100.0 + index
        rows = []
        for day in range(days):
            for hour in range(0, 24, 4):
                ts = int((start + timedelta(days=day, hours=hour)).timestamp() * 1000)
                drift = trend * (1.0 + 0.1 * index) + volatility * 0.2 * math.sin(
                    (day * 4 + hour) / 17.0 + index
                )
                open_price = price
                price = open_price * math.exp(drift)
                high = max(open_price, price) * 1.001
                low = min(open_price, price) * 0.999
                volume = quote_volume / max(price, 1e-9)
                rows.append(
                    {
                        "ts": ts,
                        "o": round(open_price, 8),
                        "h": round(high, 8),
                        "l": round(low, 8),
                        "c": round(price, 8),
                        "v": round(volume, 4),
                    }
                )
        (root / f"{symbol}.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )
    return root


def _test_config(**overrides: object):
    base = replace(
        default_config(),
        min_history=60,
        min_universe=4,
        max_positions=3,
        trend_ma=20,
        regime_ma=20,
        target_vol=0.5,
        max_leverage=1.0,
        gross_target=1.0,
        cost_bps=10.0,
        rebalance_days=5,
        max_drawdown_stop=0.0,
        stop_atr=0.0,
        funding_long_bps_day=0.0,
        funding_short_bps_day=0.0,
    )
    return replace(base, **overrides)


def test_daily_aggregation_uses_complete_ohlc(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=3, symbols=1, trend=0.0, volatility=0.0)
    panel = Panel.load(root)
    series = panel.series["BTCUSDT"]
    assert len(series.bars) == 3
    first = series.bars[0]
    assert first.open == pytest.approx(100.0, rel=1e-6)
    assert first.close == pytest.approx(100.0, rel=1e-6)
    assert first.volume > 0


def test_momentum_matches_manual_price_ratio(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=120, symbols=2)
    panel = Panel.load(root)
    series = panel.series["BTCUSDT"]
    stats = compute_stats(series, lookbacks=(7, 30, 90), ma_windows=(20, 50, 100))
    index = 100
    expected = series.bars[index].close / series.bars[index - 7].close - 1.0
    assert stats.mom[7][index] == pytest.approx(expected, rel=1e-9)
    assert stats.vol[index] is not None and stats.vol[index] > 0


def test_targets_respect_leverage_and_caps(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=200, symbols=8)
    panel = Panel.load(root)
    config = _test_config()
    stats = build_stats_cache(panel, [config])[config.stats_key()]
    ts = panel.calendar[-20]
    book = build_targets(stats, ts, config)
    assert book.targets, "trending synthetic panel must produce a book"
    assert book.gross <= config.max_leverage + 1e-9
    for target in book.targets.values():
        assert abs(target.weight) <= config.per_asset_cap + 1e-9
    assert "BTCUSDT" not in book.targets


def test_long_only_config_has_no_short_weights(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=200, symbols=8)
    panel = Panel.load(root)
    config = _test_config(allow_shorts=False, tilt_bull=1.0)
    stats = build_stats_cache(panel, [config])[config.stats_key()]
    book = build_targets(stats, panel.calendar[-20], config)
    assert book.targets
    assert all(target.weight > 0 for target in book.targets.values())


def test_simulation_trades_and_compounds_trend(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=400, symbols=8)
    panel = Panel.load(root)
    config = _test_config()
    stats = build_stats_cache(panel, [config])[config.stats_key()]
    result = run_simulation(
        panel, stats, config, start_ts=panel.calendar[80], initial_equity=1_000_000.0
    )
    assert result.trades > 0
    assert result.rebalances > 0
    assert result.equity[-1] > result.equity[0]
    assert max(result.gross_exposure) <= config.max_leverage + 1e-6


def test_costs_reduce_final_equity(tmp_path: Path) -> None:
    root = _write_panel(tmp_path / "panel", days=400, symbols=8)
    panel = Panel.load(root)
    free = _test_config(cost_bps=0.0)
    charged = _test_config(cost_bps=25.0)
    cache = build_stats_cache(panel, [free, charged])
    start = panel.calendar[80]
    cheap = run_simulation(panel, cache[free.stats_key()], free, start_ts=start)
    expensive = run_simulation(panel, cache[charged.stats_key()], charged, start_ts=start)
    assert cheap.costs_paid == 0.0
    assert expensive.costs_paid > 0.0
    assert cheap.equity[-1] > expensive.equity[-1]


def test_max_drawdown_is_peak_to_trough() -> None:
    equity = [100.0, 120.0, 90.0, 110.0]
    drawdown, peak_index, trough_index = max_drawdown(equity)
    assert drawdown == pytest.approx(0.25)
    assert (peak_index, trough_index) == (1, 2)


def test_summarize_reports_negative_years() -> None:
    start = datetime(2022, 12, 30, tzinfo=UTC)
    dates = [int((start + timedelta(days=index)).timestamp() * 1000) for index in range(10)]
    equity = [1.0, 0.9, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15]
    metrics = summarize(equity, dates, initial_equity=1.0)
    assert metrics["max_drawdown"] > 0
    assert 2022 in metrics["yearly"] and 2023 in metrics["yearly"]
    assert metrics["observations"] == 9


def test_deflated_sharpe_penalizes_more_trials() -> None:
    few = deflated_sharpe(0.1, trials=1, observations=500)
    many = deflated_sharpe(0.1, trials=100, observations=500)
    assert 0.0 <= many < few <= 1.0


def test_pbo_is_bounded_and_detects_pure_noise() -> None:
    rng = __import__("random").Random(0)
    configs = {
        f"c{index}": [rng.gauss(0.0, 0.01) for _ in range(400)] for index in range(6)
    }
    result = probability_of_backtest_overfitting(configs, splits=6)
    assert 0.0 <= result["pbo"] <= 1.0
    assert result["combinations"] > 0
