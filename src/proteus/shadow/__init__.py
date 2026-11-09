"""Phase 5: Live Forward Shadow Mode Scanner (`proteus.shadow`).

Polls live public Bitget USDT-FUTURES candles (1D for BTC/ETH Macro Compass,
4h and 15m for the high-beta tradable universe) with zero API keys, evaluating
every asset through the 7-module Project Proteus pipeline in real time.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Sequence

from proteus.engine import ProteusDistillationEngine
from proteus.market import TRADABLE_UNIVERSE
from proteus.market.bitget import BitgetPublicMarketClient
from proteus.market.bitget_ws import BitgetCandleStream


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

    # Single source of truth: the empirically traded Bitget-listed universe.
    # PROTEUS_SCAN_SYMBOLS (comma-separated) narrows or widens it per deployment.
    DEFAULT_SCAN_SYMBOLS: tuple[str, ...] = TRADABLE_UNIVERSE

    def __init__(
        self,
        engine: ProteusDistillationEngine | None = None,
        ssh_relay_host: str | None = "valarion@46.202.155.192",
        client: BitgetPublicMarketClient | None = None,
        symbols: Sequence[str] | None = None,
        stream: BitgetCandleStream | None = None,
    ) -> None:
        self.engine = engine or ProteusDistillationEngine(env={})
        self.ssh_relay_host = ssh_relay_host
        override = os.getenv("PROTEUS_SCAN_SYMBOLS", "")
        env_symbols = tuple(s.strip().upper() for s in override.split(",") if s.strip())
        self.symbols: tuple[str, ...] = tuple(
            symbols or env_symbols or self.DEFAULT_SCAN_SYMBOLS
        )
        self.client = client or BitgetPublicMarketClient(ssh_relay_host=self.ssh_relay_host)
        self.stream = stream

    @staticmethod
    def build_requests_spec(symbols: Sequence[str]) -> list[tuple[str, str, int]]:
        """Shared (symbol, granularity, limit) contract for REST and the websocket stream."""
        spec: list[tuple[str, str, int]] = [
            ("BTCUSDT", "1Dutc", 5),
            ("ETHUSDT", "1Dutc", 5),
        ]
        for sym in symbols:
            spec.append((sym, "4H", 18))
            spec.append((sym, "15m", 12))
        return spec

    def _resolve_series(
        self, batch_spec: Sequence[tuple[str, str, int]]
    ) -> dict[tuple[str, str], list]:
        """Prefer fresh websocket series; REST-fetch only what the stream cannot serve."""
        fetched: dict[tuple[str, str], list] = {}
        if self.stream is not None:
            fetched = dict(self.stream.series_for(batch_spec))
        missing = [spec for spec in batch_spec if not fetched.get((spec[0], spec[1]))]
        if missing:
            fetched.update(self.client.fetch_candles_batch(missing))
        return fetched

    def scan_live_universe(
        self,
        symbols: Sequence[str] | None = None,
    ) -> LiveShadowSnapshot:
        target_symbols = tuple(symbols) if symbols else self.symbols

        batch_spec = self.build_requests_spec(target_symbols)

        fetched = self._resolve_series(batch_spec)
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
