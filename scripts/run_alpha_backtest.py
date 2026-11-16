"""Alpha research CLI (`scripts/run_alpha_backtest.py`).

Runs the pre-registered trend/momentum portfolio against the downloaded 4H
panel and prints the honest ledger: net-of-cost metrics, walk-forward
out-of-sample results, deflated Sharpe, PBO, and the benchmarks.

    python scripts/run_alpha_backtest.py --mode report --start 2021-01-01
    python scripts/run_alpha_backtest.py --mode core
    python scripts/run_alpha_backtest.py --mode walkforward
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from proteus.alpha import (
    Panel,
    build_stats_cache,
    config_grid,
    default_config,
    iso_day,
    parse_day,
    research_report,
    run_config,
)
from proteus.alpha.research import walk_forward


def _row(name: str, metrics: dict[str, object]) -> str:
    def fmt(key: str, scale: float = 1.0, digits: int = 3) -> str:
        value = metrics.get(key)
        if value is None:
            return "n/a"
        try:
            return f"{float(value) * scale:.{digits}f}"
        except (TypeError, ValueError):
            return str(value)

    return (
        f"| {name} | {fmt('cagr', 100, 1)}% | {fmt('volatility', 100, 1)}% | "
        f"{fmt('sharpe', 1, 2)} | {fmt('max_drawdown', 100, 1)}% | "
        f"{fmt('calmar', 1, 2)} | {fmt('hit_rate', 100, 1)}% | "
        f"{fmt('cost_drag_pct', 1, 1)}% | {fmt('funding_drag_pct', 1, 1)}% |"
    )


def _print_table(results: dict[str, dict[str, object]], title: str) -> None:
    print(f"\n### {title}\n")
    print(
        "| Config | CAGR | Vol | Sharpe | MaxDD | Calmar | Hit | Cost | Funding |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    for name, metrics in sorted(
        results.items(), key=lambda item: float(item[1].get("sharpe", 0.0) or 0.0), reverse=True
    ):
        print(_row(name, metrics))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default="data/research/panel/4h")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument(
        "--mode",
        choices=("core", "grid", "walkforward", "report"),
        default="core",
    )
    parser.add_argument("--out", default="reports/alpha")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args(argv)

    panel = Panel.load(args.panel)
    start = parse_day(args.start)
    end = parse_day(args.end) if args.end else panel.calendar[-1]
    print(
        f"panel: {len(panel.series)} symbols, {iso_day(panel.calendar[0])} -> "
        f"{iso_day(panel.calendar[-1])}; test {iso_day(start)} -> {iso_day(end)}"
    )

    if args.mode == "core":
        config = default_config()
        cache = build_stats_cache(panel, [config])
        _, metrics = run_config(
            panel, config, cache[config.stats_key()], start=start, end=end
        )
        if args.json:
            print(json.dumps(metrics, indent=2, default=str))
            return 0
        _print_table({config.name: metrics}, "Core configuration (net of costs)")
        print(f"\nYearly returns: {metrics.get('yearly')}")
        print(f"Bootstrap: {metrics.get('bootstrap')}")
        print(f"Trades: {metrics.get('trades')}, rebalances: {metrics.get('rebalances')}")
        return 0

    if args.mode == "walkforward":
        configs = [default_config(), *config_grid()]
        walk = walk_forward(panel, configs, start=start, end=end)
        if args.json:
            print(json.dumps(walk, indent=2, default=str))
            return 0
        print("\n### Walk-forward selections\n")
        print("| Year | Config | Train Sharpe | Test CAGR | Test Sharpe | Test MaxDD |")
        print("|---|---|---:|---:|---:|---:|")
        for row in walk["selections"]:
            test = row["test_metrics"]
            print(
                f"| {row['year']} | {row['config']} | {row['train_sharpe']} | "
                f"{float(test.get('cagr', 0.0) or 0.0) * 100:.1f}% | "
                f"{test.get('sharpe')} | {float(test.get('max_drawdown', 0.0) or 0.0) * 100:.1f}% |"
            )
        oos = walk["oos_metrics"]
        _print_table({"walk-forward OOS": oos}, "Stitched out-of-sample")
        print(f"\nYearly OOS: {oos.get('yearly')}")
        return 0

    report = research_report(panel, start=start, end=end, output_dir=Path(args.out))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0
    core = report["core"]["metrics"]
    _print_table({"core": core}, "Core configuration (net of costs)")
    print(
        f"\nDeflated Sharpe: {core.get('deflated_sharpe')} search-adjusted "
        f"({report['overfitting']['trials']} trials); "
        f"{core.get('deflated_sharpe_preregistered')} pre-registered; "
        f"PBO={report['overfitting']['pbo'].get('pbo')}"
    )
    holdout = report.get("holdout_2024", {}).get("metrics", {})
    if holdout.get("observations"):
        print(
            f"Holdout 2024-01-01 -> {holdout.get('end')}: "
            f"CAGR {float(holdout.get('cagr', 0.0)) * 100:.1f}%, "
            f"Sharpe {holdout.get('sharpe')}, "
            f"MaxDD {float(holdout.get('max_drawdown', 0.0)) * 100:.1f}%"
        )
    print(f"Bootstrap: {core.get('bootstrap')}")
    print(f"Yearly: {core.get('yearly')}")
    _print_table(
        {name: row["metrics"] for name, row in report["grid"].items()},
        f"Grid ({len(report['grid'])} configurations)",
    )
    oos = report["walk_forward"]["oos_metrics"]
    _print_table({"walk-forward OOS": oos}, "Stitched out-of-sample")
    print(f"\nYearly OOS: {oos.get('yearly')}")
    print("\nBenchmarks:")
    for name, bench in report["benchmarks"].items():
        bm = bench["metrics"]
        if bm.get("observations"):
            print(
                f"  {name}: CAGR {float(bm['cagr']) * 100:.1f}%, "
                f"Sharpe {bm['sharpe']}, MaxDD {float(bm['max_drawdown']) * 100:.1f}%"
            )
    print(f"\nReport written to {Path(args.out) / 'alpha-research.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
