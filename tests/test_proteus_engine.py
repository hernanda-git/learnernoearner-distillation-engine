"""End-to-end unit and invariant verification suite for Project Proteus."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from proteus import (
    Action,
    BoundingBox,
    Candle,
    Direction,
    MacroRegime,
    OrderMode,
    ProteusDistillationEngine,
    SetupArchetype,
    TradeState,
)
from proteus.benchmark import BehavioralParityBenchmark
from proteus.compass import MacroCompassGate
from proteus.engine import AirGapSecurityError
from proteus.fsm import TradeLifecycleFSM
from proteus.geometry import StructuralGeometryEngine
from proteus.market import MultiTimeframeStore, normalize_base_symbol
from proteus.params import OrderParameterSynthesizer
from proteus.policy import CognitivePolicyGate
from proteus.vision import VisualSaliencyAgent
from scripts.extract_corpus_readonly import extract_sqlite_readonly


def _make_candle(
    symbol: str,
    timeframe: str,
    ts: datetime,
    o: str,
    h: str,
    l: str,
    c: str,
) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp_utc=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal("1000"),
    )


def test_air_gap_security_blocks_live_credentials() -> None:
    with pytest.raises(AirGapSecurityError, match="BITGET_API_KEY"):
        ProteusDistillationEngine(env={"BITGET_API_KEY": "bg_live_secret"})

    with pytest.raises(AirGapSecurityError, match="SECRETCONSTANTS__TRIPLEDESKEY"):
        ProteusDistillationEngine(env={"SECRETCONSTANTS__TRIPLEDESKEY": "3des_live"})

    # Clean environment initializes without error
    engine = ProteusDistillationEngine(env={})
    assert engine is not None


def test_market_universe_and_negative_space_sampling() -> None:
    assert normalize_base_symbol("$1000PEPE/USDT:USDT") == "PEPE"
    assert MultiTimeframeStore.is_tradable_symbol("WLD") is True
    assert MultiTimeframeStore.is_tradable_symbol("$PEPE") is True
    assert MultiTimeframeStore.is_tradable_symbol("BTC") is False
    assert MultiTimeframeStore.is_tradable_symbol("ETH/USDT") is False

    store = MultiTimeframeStore()
    t0 = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
    candles = [
        _make_candle("WLD", "15m", t0 + timedelta(minutes=15 * i), "2.00", "2.05", "1.95", "2.01")
        for i in range(-20, 21)
    ]
    assert store.ingest(candles) == 41

    negatives = store.sample_negative_space("WLD", "15m", [t0], exclusion_radius=timedelta(hours=2))
    # 2h = 8 bars on each side + center bar = 17 excluded bars out of 41 -> 24 negative bars
    assert len(negatives) == 24
    assert all(abs((c.timestamp_utc - t0).total_seconds()) > 7200 for c in negatives)


def test_macro_compass_regime_and_directional_invariants() -> None:
    compass = MacroCompassGate()
    t0 = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

    btc_prior = [
        _make_candle("BTC", "1D", t0 - timedelta(days=3), "82000", "85000", "81000", "83500"),
        _make_candle("BTC", "1D", t0 - timedelta(days=2), "83500", "86000", "82000", "84000"),
        _make_candle("BTC", "1D", t0 - timedelta(days=1), "84000", "85500", "82500", "83800"),
    ]

    # 1. Bullish expansion (close > open and close > 3d midpoint 83500)
    bullish_day = _make_candle("BTC", "1D", t0, "83800", "87200", "83600", "86500")
    regime_bull = compass.evaluate_regime([*btc_prior, bullish_day])
    assert regime_bull == MacroRegime.BULLISH_EXPANSION

    # Invariant 2: Never output a Short signal on a high-beta token if BTC 1D is expanding upwards
    allowed_short, _ = compass.is_direction_allowed("WLD", Direction.SHORT, regime_bull)
    assert allowed_short is False
    allowed_long, _ = compass.is_direction_allowed("WLD", Direction.LONG, regime_bull)
    assert allowed_long is True

    # 2. Breakdown below 3d support (81000) freezes all altcoin Longs
    breakdown_day = _make_candle("BTC", "1D", t0, "82000", "82500", "79500", "80200")
    regime_break = compass.evaluate_regime([*btc_prior, breakdown_day])
    assert regime_break == MacroRegime.BREAKDOWN
    allowed_long_break, _ = compass.is_direction_allowed("WLD", Direction.LONG, regime_break)
    assert allowed_long_break is False

    # 3. BTC and ETH are never traded directly
    btc_allowed, _ = compass.is_direction_allowed("BTC", Direction.LONG, regime_bull)
    assert btc_allowed is False


def test_3tier_geometry_and_no_mans_land_abstention() -> None:
    geom_engine = StructuralGeometryEngine()
    policy = CognitivePolicyGate()
    t0 = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)  # London Open (08:00 UTC)

    # 72h range: Range Low = 2140, Range High = 2700 -> Mid Range = 2420
    pool = [
        _make_candle("ENA", "4h", t0 - timedelta(hours=12), "2300", "2700", "2250", "2500"),
        _make_candle("ENA", "4h", t0 - timedelta(hours=8), "2500", "2550", "2140", "2350"),
    ]

    # Case A: Floating in No-Man's Land (2560 is halfway between Mid 2420 and High 2700)
    floating_bar = _make_candle("ENA", "15m", t0, "2555", "2570", "2550", "2560")
    geom_float = geom_engine.compute("ENA", pool, execution_candle=floating_bar)
    assert geom_float.range_high == Decimal("2700")
    assert geom_float.range_low == Decimal("2140")
    assert geom_float.mid_range == Decimal("2420")
    assert geom_float.in_no_mans_land is True

    decision_float = policy.evaluate(geom_float, MacroRegime.RANGE_BOUND, t0)
    assert decision_float.action == Action.ABSTAIN
    assert decision_float.abstain_prob >= 0.85

    # Case B: Midrange retest from above -> ENTER_LONG with LIMIT order mode
    retest_bar = _make_candle("ENA", "15m", t0, "2435", "2450", "2415", "2438")
    geom_retest = geom_engine.compute("ENA", pool, execution_candle=retest_bar)
    assert geom_retest.reclaimed_midrange is True
    assert geom_retest.in_no_mans_land is False

    decision_retest = policy.evaluate(geom_retest, MacroRegime.BULLISH_EXPANSION, t0)
    assert decision_retest.action == Action.ENTER_LONG
    assert decision_retest.archetype == SetupArchetype.MIDRANGE_RETEST
    assert decision_retest.order_mode == OrderMode.LIMIT

    # Case C: Range Low liquidity sweep with bullish rejection -> ENTER_LONG with MARKET order mode
    sweep_bar = _make_candle("ENA", "15m", t0, "2150", "2175", "2125", "2165")
    geom_sweep = geom_engine.compute("ENA", pool, execution_candle=sweep_bar)
    assert geom_sweep.swept_low is True
    decision_sweep = policy.evaluate(geom_sweep, MacroRegime.RANGE_BOUND, t0)
    assert decision_sweep.action == Action.ENTER_LONG
    assert decision_sweep.archetype == SetupArchetype.LIQUIDITY_SWEEP_RECLAIM
    assert decision_sweep.order_mode == OrderMode.MARKET


def test_parameter_synthesizer_and_meme_power_of_10_scaler() -> None:
    synth = OrderParameterSynthesizer()
    t0 = datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)

    # Shorthand quote 0.50 vs live reference 0.0000050 (10^-5 scale)
    scaled_price, factor = synth.resolve_power_of_10_scale(
        Decimal("0.50"), Decimal("0.00000502")
    )
    assert scaled_price == Decimal("0.0000050")
    assert factor == 100000

    # End-to-end engine run on WLD midrange retest with 2.6% structural risk & 4.56R TP
    engine = ProteusDistillationEngine(env={})
    btc_1d = [
        _make_candle("BTC", "1D", t0 - timedelta(days=2), "82000", "84000", "81000", "83000"),
        _make_candle("BTC", "1D", t0 - timedelta(days=1), "83000", "85000", "82000", "84500"),
        _make_candle("BTC", "1D", t0, "84500", "86500", "84000", "86000"),
    ]
    wld_72h = [
        _make_candle("WLD", "4h", t0 - timedelta(hours=24), "1.90", "2.20", "1.80", "2.05"),
    ]
    # Midrange = 2.00; 15m retests 1.995 with swing low at 1.952 (~2.55% risk)
    wld_15m = [
        _make_candle("WLD", "15m", t0 - timedelta(minutes=15), "2.01", "2.02", "1.952", "2.005"),
        _make_candle("WLD", "15m", t0, "2.005", "2.015", "1.995", "2.000"),
    ]

    regime, decision, setup = engine.evaluate_bar("WLD", wld_72h, wld_15m, btc_1d)
    assert regime == MacroRegime.BULLISH_EXPANSION
    assert decision.action == Action.ENTER_LONG
    assert setup is not None
    assert Decimal("0.50") <= setup.risk_pct <= Decimal("5.00")
    assert setup.planned_rr == Decimal("4.56")
    assert setup.stop_loss < setup.entry_price < setup.take_profit


def test_in_flight_fsm_breakeven_bedtime_and_lexicon() -> None:
    fsm = TradeLifecycleFSM()
    engine = ProteusDistillationEngine(env={})
    t0 = datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc)

    btc_1d = [
        _make_candle("BTC", "1D", t0 - timedelta(days=1), "82000", "85000", "81000", "84000"),
        _make_candle("BTC", "1D", t0, "84000", "86000", "83500", "85500"),
    ]
    wld_72h = [_make_candle("WLD", "4h", t0 - timedelta(hours=12), "1.80", "2.20", "1.80", "2.02")]
    wld_15m = [_make_candle("WLD", "15m", t0, "2.00", "2.01", "1.95", "2.00")]

    _, _, setup = engine.evaluate_bar("WLD", wld_72h, wld_15m, btc_1d)
    assert setup is not None

    pos = fsm.open_position(setup, t0)
    assert pos.state == TradeState.ACTIVE

    # Advance price to +1.1R during NY session (16:00 UTC) -> migrates SL to entry
    risk = setup.entry_price - setup.stop_loss
    price_1_1r = setup.entry_price + (risk * Decimal("1.10"))
    pos_be = fsm.on_tick(pos, price_1_1r, t0.replace(hour=16))
    assert pos_be.state == TradeState.BREAKEVEN_PROTECTED
    assert pos_be.current_sl == setup.entry_price

    # Cross into bedtime window (21:30 UTC) while at +1.2R -> derisks 50%
    price_1_2r = setup.entry_price + (risk * Decimal("1.20"))
    pos_bed = fsm.on_tick(pos_be, price_1_2r, t0.replace(hour=21, minute=30))
    assert pos_bed.state == TradeState.BEDTIME_DERISKED
    assert pos_bed.remaining_size_fraction == Decimal("0.50")
    assert pos_bed.realized_r > Decimal("0.00")

    # Linguistic command translation ("full tp booked at 3R +")
    pos_closed = fsm.apply_linguistic_command(
        pos_bed, "full tp booked at 3R +", t0.replace(hour=22)
    )
    assert pos_closed.state == TradeState.CLOSED_TP
    assert pos_closed.remaining_size_fraction == Decimal("0.00")


def test_visual_saliency_and_behavioral_parity_scorecard(tmp_path: Path) -> None:
    vision = VisualSaliencyAgent()
    b1 = BoundingBox(0.0, 0.45, 1.0, 0.55)
    b2 = BoundingBox(0.0, 0.46, 1.0, 0.55)
    iou, passed = vision.evaluate_saliency_parity(b1, b2)
    assert iou >= 0.80
    assert passed is True

    scorecard = BehavioralParityBenchmark.evaluate(
        directional_concordance=0.94,
        setup_recall=0.82,
        spatial_iou=0.86,
        abstention_accuracy=0.97,
        sl_proximity_delta_pct=0.28,
        tp_proximity_delta_pct=0.65,
        median_timing_delta_seconds=-2.5,
    )
    assert scorecard.bps >= 0.85
    assert scorecard.passed is True

    # Verify read-only SQLite snapshot extractor
    db_file = tmp_path / "snapshot.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE canonical_signals (id INTEGER PRIMARY KEY, symbol TEXT, direction TEXT)")
        conn.execute("INSERT INTO canonical_signals VALUES (1, 'WLD', 'LONG')")
        conn.commit()

    out_dir = tmp_path / "exported"
    manifest = extract_sqlite_readonly(db_file, out_dir)
    assert manifest["tables"]["canonical_signals"]["rows"] == 1
    assert (out_dir / "canonical_signals.jsonl").exists()


def test_empirical_corpus_replay_all_97_signals_and_784_messages() -> None:
    from proteus.replay import EmpiricalCorpusReplay

    replay = EmpiricalCorpusReplay()
    assert replay.resolve_update_token("sl to entry $ETHFI", "SLUSDT") == "ETHFI"

    report = replay.run()
    assert report.total_messages == 784
    assert report.total_signals == 97
    assert report.total_management_updates == 47
    assert report.long_count == 78
    assert report.short_count == 19
    assert report.median_sl_pct_all == 2.60
    assert report.median_sl_pct_long == 2.67
    assert report.median_sl_pct_short == 2.17
    assert report.median_rr_long == 4.87
    assert report.median_rr_short == 4.46
    assert report.median_mins_to_be == 119.1
    assert report.median_mins_to_tp1 == 123.6
    assert report.parity_metrics.bps >= 0.85
    assert report.parity_metrics.passed is True


def test_phase1_and_3_5097_bar_bayesian_cognitive_policy() -> None:
    from proteus.market.lakehouse import NegativeSpaceDatasetBuilder
    from proteus.policy.bayesian import BayesianCognitivePolicy

    builder = NegativeSpaceDatasetBuilder()
    dataset = builder.build_dataset(negative_count=5000)
    assert len(dataset) == 5097

    model = BayesianCognitivePolicy().fit(dataset)
    metrics = model.evaluate_dataset(dataset)
    assert metrics.total_bars == 5097
    assert metrics.positive_signals == 97
    assert metrics.negative_bars == 5000
    assert metrics.abstention_accuracy >= 0.99
    assert metrics.setup_recall >= 0.95
    assert metrics.directional_concordance == 1.0


def test_phase2_tradingview_rgb_box_extractor() -> None:
    from proteus.vision.chart_extractor import TradingViewBoxExtractor

    # Build a 100x100 synthetic TradingView candlestick canvas with Long TP & SL boxes
    # Price axis y=0 at bottom (row 99), y=1 at top (row 0).
    # Entry at y_norm = 0.30 (row 70), Stop box y_norm [0.20, 0.30] (rows 70..80),
    # Profit box y_norm [0.30, 0.75] (rows 25..70) -> Implied RR = 0.45 / 0.10 = 4.50R
    grid = [[(19, 23, 34) for _ in range(100)] for _ in range(100)]
    for r_idx in range(25, 70):
        for c_idx in range(30, 80):
            grid[r_idx][c_idx] = (8, 153, 129)  # TradingView teal profit zone
    for r_idx in range(70, 80):
        for c_idx in range(30, 80):
            grid[r_idx][c_idx] = (242, 54, 69)  # TradingView crimson stop zone

    extractor = TradingViewBoxExtractor()
    human_gt = BoundingBox(0.30, 0.30, 0.80, 0.75)
    res = extractor.extract_from_rgb_grid(grid, human_profit_box=human_gt)
    assert res.implied_direction == "LONG"
    assert 4.2 <= res.implied_rr <= 4.9
    assert res.spatial_iou_vs_human >= 0.90


def test_phase4_comparative_97_signal_backtest_simulator() -> None:
    from proteus.backtest import LifecycleBacktestSimulator

    sim = LifecycleBacktestSimulator()
    report = sim.run_comparative_backtest()
    assert report.naive_set_and_forget.total_trades == 97
    assert report.proteus_distilled_fsm.total_trades == 97
    assert report.proteus_distilled_fsm.total_realized_r > report.naive_set_and_forget.total_realized_r
    assert report.proteus_distilled_fsm.profit_factor > report.naive_set_and_forget.profit_factor * 3.5
    assert report.drawdown_reduction_r > 12.0
