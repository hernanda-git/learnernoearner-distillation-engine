"""Phase 5: Live Forward Shadow Mode Scanner (`proteus.shadow`).

Polls live public Bitget USDT-FUTURES candles (1D for BTC/ETH Macro Compass,
4h and 15m for the high-beta tradable universe) with zero API keys, evaluating
every asset through the 7-module Project Proteus pipeline in real time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Sequence

from proteus.engine import ProteusDistillationEngine
from proteus.market.lakehouse import fetch_public_bitget_candles_batch


@dataclass(frozen=True)
class AssetShadowState:
    symbol: str
    last_close: str
    range_low_72h: str
    mid_range_72h: str
    range_high_72h: str
    equilibrium_width_pct: str
    swept_low: bool
    swept_high: bool
    reclaimed_midrange: bool
    in_no_mans_land: bool
    action: str
    confidence: float
    abstain_prob: float
    archetype: str
    order_mode: str | None
    synthesized_sl: str | None
    synthesized_tp: str | None
    rationale: str


@dataclass(frozen=True)
class LiveShadowSnapshot:
    scanned_at_utc: str
    btc_1d_close: str
    eth_1d_close: str
    macro_regime: str
    universe_evaluated: int
    active_entries: int
    abstentions: int
    states: list[AssetShadowState]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ForwardShadowScanner:
    """Executes real-time shadow scans across BTC/ETH and the high-beta universe."""

    DEFAULT_SCAN_SYMBOLS: tuple[str, ...] = (
        "WLD",
        "PUMP",
        "ENA",
        "ZEC",
        "INJ",
        "PENGU",
        "MAGIC",
        "NEAR",
        "PEPE",
    )

    def __init__(
        self,
        engine: ProteusDistillationEngine | None = None,
        ssh_relay_host: str | None = "valarion@46.202.155.192",
    ) -> None:
        self.engine = engine or ProteusDistillationEngine(env={})
        self.ssh_relay_host = ssh_relay_host

    def scan_live_universe(
        self,
        symbols: Sequence[str] | None = None,
    ) -> LiveShadowSnapshot:
        target_symbols = symbols or self.DEFAULT_SCAN_SYMBOLS

        batch_spec: list[tuple[str, str, int]] = [
            ("BTCUSDT", "1Dutc", 5),
            ("ETHUSDT", "1Dutc", 5),
        ]
        for sym in target_symbols:
            batch_spec.append((sym, "4H", 18))
            batch_spec.append((sym, "15m", 12))

        fetched = fetch_public_bitget_candles_batch(
            batch_spec, ssh_relay_host=self.ssh_relay_host
        )
        btc_1d = fetched.get(("BTCUSDT", "1Dutc"), [])
        eth_1d = fetched.get(("ETHUSDT", "1Dutc"), [])

        regime = self.engine.compass.evaluate_regime(btc_1d, eth_1d)
        btc_close = str(btc_1d[-1].close) if btc_1d else "N/A"
        eth_close = str(eth_1d[-1].close) if eth_1d else "N/A"

        states: list[AssetShadowState] = []
        active_entries = 0
        abstentions = 0

        for sym in target_symbols:
            candles_4h = fetched.get((sym, "4H"), [])
            candles_15m = fetched.get((sym, "15m"), [])
            if not candles_4h or not candles_15m:
                continue

            exec_candle = candles_15m[-1]
            geom = self.engine.geometry.compute(sym, candles_4h, execution_candle=exec_candle)
            _, decision, setup = self.engine.evaluate_bar(
                symbol=sym,
                candles_72h=candles_4h,
                recent_15m_candles=candles_15m,
                btc_daily_candles=btc_1d,
                eth_daily_candles=eth_1d,
            )

            if decision.action.value == "ABSTAIN":
                abstentions += 1
            else:
                active_entries += 1

            states.append(
                AssetShadowState(
                    symbol=sym,
                    last_close=str(exec_candle.close),
                    range_low_72h=str(geom.range_low),
                    mid_range_72h=str(geom.mid_range),
                    range_high_72h=str(geom.range_high),
                    equilibrium_width_pct=f"{geom.equilibrium_width_pct}%",
                    swept_low=geom.swept_low,
                    swept_high=geom.swept_high,
                    reclaimed_midrange=geom.reclaimed_midrange,
                    in_no_mans_land=geom.in_no_mans_land,
                    action=decision.action.value,
                    confidence=decision.confidence,
                    abstain_prob=decision.abstain_prob,
                    archetype=decision.archetype.value,
                    order_mode=decision.order_mode.value if decision.order_mode else None,
                    synthesized_sl=str(setup.stop_loss) if setup else None,
                    synthesized_tp=str(setup.take_profit) if setup else None,
                    rationale=decision.rationale,
                )
            )

        return LiveShadowSnapshot(
            scanned_at_utc=datetime.now(timezone.utc).isoformat(),
            btc_1d_close=btc_close,
            eth_1d_close=eth_close,
            macro_regime=regime.value,
            universe_evaluated=len(states),
            active_entries=active_entries,
            abstentions=abstentions,
            states=states,
        )
