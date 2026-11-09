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
    assert report.real_candle_audit.resolved_signals == 87
    assert report.real_candle_audit.reached_1r_before_sl == 47
    assert report.real_candle_audit.whipsaw_reversed_to_sl_after_1r == 29
    assert report.real_candle_audit.whipsaw_rate_of_1r_winners_pct == 61.7
    assert report.real_candle_audit.silent_stop_out_share_pct == 56.5


def test_real_284_screenshot_vision_corpus_annotations() -> None:
    from proteus.vision.chart_extractor import VisionCorpusAnalyzer

    summary = VisionCorpusAnalyzer.summarize_corpus()
    assert summary.total_screenshots == 284
    assert summary.light_theme_count == 216
    assert summary.dark_theme_count == 68
    assert summary.rr_projection_box_count == 238
    assert summary.rr_projection_box_pct == 83.8
    assert summary.sr_zone_box_count == 129


def test_virtual_paper_exchange_admits_and_steps_shadow_positions(tmp_path: Path) -> None:
    import json
    from proteus.paper import VirtualPaperExchange
    from proteus.shadow import AssetShadowState, LiveShadowSnapshot

    snap_path = Path(__file__).resolve().parents[1] / "benchmarks" / "live_shadow_snapshot.json"
    raw = json.loads(snap_path.read_text(encoding="utf-8"))
    snapshot = LiveShadowSnapshot(
        scanned_at_utc=raw["scanned_at_utc"],
        btc_1d_close=raw["btc_1d_close"],
        eth_1d_close=raw["eth_1d_close"],
        macro_regime=raw["macro_regime"],
        universe_evaluated=raw["universe_evaluated"],
        active_entries=raw["active_entries"],
        abstentions=raw["abstentions"],
        states=[AssetShadowState(**s) for s in raw["states"]],
    )

    ledger_file = tmp_path / "paper_ledger.json"
    exchange = VirtualPaperExchange(ledger_path=ledger_file)
    ledger = exchange.process_shadow_snapshot(snapshot)
    assert ledger.open_positions_count == snapshot.active_entries
    assert ledger.current_equity_usdt <= 1000.0
    hist = exchange.run_historical_paper_simulation()
    assert hist["proteus_distilled_clone"]["ending_equity_usdt"] == 2998.2
    assert hist["proteus_distilled_clone"]["max_drawdown_pct"] == 4.0
    assert hist["naive_set_and_forget"]["max_drawdown_pct"] == 30.28


def test_phase6_synthetic_tradingview_rgb_renderer() -> None:
    from proteus.geometry import StructuralGeometryEngine
    from proteus.vision.renderer import SyntheticTradingViewRenderer

    t0 = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
    bars = [
        _make_candle(
            "INJ",
            "15m",
            t0 + timedelta(minutes=15 * i),
            "8.05",
            "8.50" if i == 2 else "8.20",
            "7.70" if i == 1 else "8.00",
            "8.13",
        )
        for i in range(16)
    ]
    geom = StructuralGeometryEngine().compute("INJ", bars)
    renderer = SyntheticTradingViewRenderer(dark_theme=True)
    extraction = renderer.render_and_extract_iou(
        candles=bars,
        geometry=geom,
        direction=Direction.LONG,
        entry_price=Decimal("8.13"),
        stop_loss=Decimal("7.92"),
        take_profit=Decimal("9.09"),
    )
    assert extraction.implied_direction == "LONG"
    assert extraction.spatial_iou_vs_human >= 0.85


def test_phase6_shadow_lead_time_comparator(tmp_path: Path) -> None:
    from proteus.shadow.lead_time import ShadowLeadTimeComparator

    comp = ShadowLeadTimeComparator(log_path=tmp_path / "lead_log.json")
    summary = comp.evaluate_shadow_lead_time()
    assert summary.evaluated_pairs == 25
    assert summary.median_delta_t_seconds < 0.0
    assert summary.front_run_or_simultaneous_rate_pct == 100.0


def test_phase6_fee_model_and_margin_velocity_slot_eviction(tmp_path: Path) -> None:
    from proteus.paper import VirtualPaperExchange
    from proteus.shadow import AssetShadowState, LiveShadowSnapshot

    def _state(sym: str, conf: float) -> AssetShadowState:
        return AssetShadowState(
            symbol=sym,
            last_close="10.00",
            range_low_72h="9.50",
            mid_range_72h="10.00",
            range_high_72h="10.50",
            equilibrium_width_pct="10.5%",
            swept_low=False,
            swept_high=False,
            reclaimed_midrange=True,
            in_no_mans_land=False,
            action="ENTER_LONG",
            confidence=conf,
            abstain_prob=round(1.0 - conf, 2),
            archetype="MIDRANGE_RETEST",
            order_mode="LIMIT",
            synthesized_sl="9.74",
            synthesized_tp="11.18",
            rationale="Midrange retest",
        )

    snap = LiveShadowSnapshot(
        scanned_at_utc="2026-11-09T08:00:00+00:00",
        btc_1d_close="75000",
        eth_1d_close="2150",
        macro_regime="RANGE_BOUND",
        universe_evaluated=4,
        active_entries=4,
        abstentions=0,
        states=[
            _state("WLD", 0.72),
            _state("ENA", 0.78),
            _state("INJ", 0.84),
            _state("PEPE", 0.91),
        ],
    )

    exchange = VirtualPaperExchange(
        ledger_path=tmp_path / "evict_ledger.json",
        max_open_positions=3,
    )
    ledger = exchange.process_shadow_snapshot(snap)
    # Max 3 open positions enforced; WLD (lowest confidence 0.72, 0.00R stalled) evicted for PEPE (0.91)
    assert ledger.open_positions_count == 3
    assert ledger.margin_evictions_count == 1
    assert ledger.positions["WLD"].state == "CLOSED_EARLY"
    assert ledger.positions["WLD"].eviction_reason == "margin_velocity_eviction_for_PEPE"
    assert ledger.total_fees_paid_usdt > 0.0


def test_constitutional_identity_guard_and_anti_indicator_purity(tmp_path: Path) -> None:
    from proteus.constitution import (
        ConstitutionalIdentityGuard,
        ConstitutionalParameters,
        IdentityDriftError,
    )

    # 1. Verify entire src/proteus/ codebase has zero lagging retail TA indicators
    pure, count = ConstitutionalIdentityGuard.verify_codebase_purity()
    assert pure is True
    assert count >= 14

    # 2. Verify injecting a lagging indicator into a module raises IdentityDriftError
    fake_src = tmp_path / "fake_src"
    fake_src.mkdir()
    (fake_src / "bad_bot.py").write_text("def compute_rsi(prices): return 50\n", encoding="utf-8")
    with pytest.raises(IdentityDriftError, match="Forbidden lagging retail indicator"):
        ConstitutionalIdentityGuard.verify_codebase_purity(fake_src)

    # 3. Verify breaking the 80/20 conviction gap or SL asymmetry raises IdentityDriftError
    with pytest.raises(IdentityDriftError, match="Directional asymmetry violation"):
        ConstitutionalIdentityGuard.validate_parameters(
            ConstitutionalParameters(
                long_conviction_threshold=0.72,
                short_conviction_threshold=0.80,
            )
        )
    with pytest.raises(IdentityDriftError, match="Stop-loss asymmetry violation"):
        ConstitutionalIdentityGuard.validate_parameters(
            ConstitutionalParameters(
                median_sl_long_pct=0.0200,
                median_sl_short_pct=0.0250,
            )
        )


def test_bounded_self_corrector_fine_tuning_and_auto_rollback(tmp_path: Path) -> None:
    from proteus.constitution import BoundedSelfCorrector, IdentityDriftError

    ckpt = tmp_path / "constitutional_checkpoint.json"
    corrector = BoundedSelfCorrector(checkpoint_path=ckpt)
    base = corrector.load_active_parameters()
    assert base.generation == 1

    # 1. Valid fine-tune shrinks smoothly toward Constitutional Anchor and increments generation
    outcome_ok = corrector.propose_fine_tune(
        observed_estimates={
            "median_sl_long_pct": 0.0285,
            "median_rr_long": 5.10,
        },
        learning_rate=0.20,
        candidate_bps=0.96,
    )
    assert outcome_ok.accepted is True
    assert outcome_ok.generation == 2
    assert 0.0267 < outcome_ok.active_params.median_sl_long_pct < 0.0285
    assert 4.87 < outcome_ok.active_params.median_rr_long < 5.10

    # 2. Candidate update that degrades BPS below 0.85 automatically rolls back to gen 2
    outcome_bad_bps = corrector.propose_fine_tune(
        observed_estimates={"median_rr_long": 5.40},
        learning_rate=0.20,
        candidate_bps=0.78,
    )
    assert outcome_bad_bps.accepted is False
    assert outcome_bad_bps.generation == 2
    assert "Automatic Turing rollback" in outcome_bad_bps.reason

    # 3. Strict mode rejects raw out-of-corridor proposals immediately
    with pytest.raises(IdentityDriftError, match="violates corridor"):
        corrector.propose_fine_tune(
            observed_estimates={"no_mans_land_abstain_prob": 0.40},
            strict_mode=True,
        )


def test_web_ui_dashboard_payload_and_template() -> None:
    from proteus.web import build_dashboard_payload
    from proteus.web.ui_template import INDEX_HTML

    payload = build_dashboard_payload()
    assert payload["constitution"]["pure_codebase"] is True
    assert payload["turing_replay"]["total_signals"] == 97
    assert payload["vision_summary"]["total_screenshots"] == 284
    assert len(payload["signals_ledger"]) == 97
    assert len(payload["management_updates"]) == 47
    assert "PROJECT PROTEUS" in INDEX_HTML


def test_self_monitoring_watchdog_and_latch_healer(tmp_path: Path) -> None:
    from proteus.monitor import SelfMonitoringWatchdog

    state_file = tmp_path / "monitor.json"
    watchdog = SelfMonitoringWatchdog(state_path=state_file)

    # 1. Leak in env triggers LATCHED_HALT
    snap_bad = watchdog.evaluate_and_heal(env={"BITGET_API_KEY": "leaked"})
    assert snap_bad.overall_status == "LATCHED_HALT"
    assert snap_bad.latch_active is True
    assert snap_bad.consecutive_healthy_cycles == 0

    # 2. 6 consecutive healthy cycles automatically heal the latch (LatchHealer)
    for i in range(1, 6):
        snap_mid = watchdog.evaluate_and_heal(env={})
        assert snap_mid.latch_active is True
        assert snap_mid.consecutive_healthy_cycles == i

    snap_healed = watchdog.evaluate_and_heal(env={})
    assert snap_healed.latch_active is False
    assert snap_healed.total_healed_events == 1
    assert snap_healed.overall_status in ("HEALTHY", "DEGRADED_WARN")


def test_agentic_self_improver_and_faj1_hash_chain_journal(tmp_path: Path) -> None:
    from proteus.constitution import BoundedSelfCorrector
    from proteus.evolver import AgenticSelfImprover
    from proteus.monitor import SelfMonitoringWatchdog

    ckpt = tmp_path / "const.json"
    mon_state = tmp_path / "mon.json"
    journal_file = tmp_path / "journal.json"

    watchdog = SelfMonitoringWatchdog(state_path=mon_state)
    corrector = BoundedSelfCorrector(checkpoint_path=ckpt)
    improver = AgenticSelfImprover(
        journal_path=journal_file,
        corrector=corrector,
        watchdog=watchdog,
    )

    entry1 = improver.run_improvement_cycle(trigger_source="unit_test_1")
    assert entry1.sequence_id == 1
    assert entry1.accepted is True
    assert len(entry1.agent_traces) == 4

    entry2 = improver.run_improvement_cycle(
        trigger_source="unit_test_2_bad_proposal",
        custom_proposals={"no_mans_land_abstain_prob": 0.30},
    )
    assert entry2.sequence_id == 2
    assert entry2.accepted is False
    assert entry2.prev_hash == entry1.entry_hash

    valid, length = improver.verify_journal_hash_chain()
    assert valid is True
    assert length == 2


def test_fractal_structure_engine_beats_naive_72h_on_92_real_bitget_series() -> None:
    from proteus.geometry.fractal import FractalHorizontalStructureEngine

    engine = FractalHorizontalStructureEngine()
    report = engine.evaluate_real_corpus_blind_recall()
    assert report.evaluated_real_series == 92
    # Naive 72h rolling box recalls only ~25%, while Multi-Scale Fractal recalls >95% with zero lookahead
    assert report.naive_72h_recall_pct < 35.0
    assert report.fractal_recall_pct >= 95.0
    assert report.short_mean_24h_ret_pct > report.long_mean_24h_ret_pct * 2.0


def test_cross_sectional_attention_and_thesis_memory_reentry() -> None:
    import json
    from proteus.fsm.thesis_memory import ThesisMemoryTracker
    from proteus.market.attention import CrossSectionalAttentionScorer

    raw_path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "corpus"
        / "real_1h_candles_by_signal.json"
    )
    series = json.loads(raw_path.read_text(encoding="utf-8"))
    first_valid = next(r for r in series if len(r["pre_72h_candles"]) >= 36)

    scorer = CrossSectionalAttentionScorer()
    att = scorer.score_candles(first_valid["symbol"], first_valid["pre_72h_candles"], hour_utc=14)
    assert 0.0 <= att.score <= 1.0

    tracker = ThesisMemoryTracker()
    t0 = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    mem = tracker.record_stop_out(
        symbol="WLD",
        direction="LONG",
        stopped_entry=0.417,
        stopped_sl=0.408,
        lower_demand_level=0.387,
        timestamp_utc=t0,
    )
    assert mem.state == "WATCHING_LOWER_DEMAND_REENTRY"

    should_reenter, boost, reason = tracker.evaluate_reentry_opportunity(
        "WLD", current_price=0.388, now_utc=t0 + timedelta(hours=4)
    )
    assert should_reenter is True
    assert boost == 0.10
    assert "0.387" in reason
