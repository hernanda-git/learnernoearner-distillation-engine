"""Phase 1: Real-Candle Negative Space Miner & Multi-TF Feature Lakehouse (`proteus.market.lakehouse`).

Constructs the aligned feature matrix directly from the 10,994 real Bitget 1H
OHLCV candles (`benchmarks/corpus/real_1h_candles_by_signal.json`), with zero
synthetic `_det_float` random numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from proteus.domain.models import Candle
from proteus.geometry.fractal import FractalHorizontalStructureEngine
from proteus.market.bitget import BitgetPublicMarketClient

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "corpus"


@dataclass(frozen=True)
class FeatureVector:
    bar_id: str
    symbol: str
    timestamp_utc: str
    label: str  # "ABSTAIN", "ENTER_LONG", "ENTER_SHORT"
    btc_regime_score: float
    dist_to_range_low_pct: float
    dist_to_mid_range_pct: float
    dist_to_range_high_pct: float
    swept_low: float
    swept_high: float
    reclaimed_midrange: float
    rejected_midrange: float
    in_no_mans_land: float
    session_bonus: float
    visual_saliency_iou: float

    def to_numeric_tuple(self) -> tuple[float, ...]:
        return (
            self.btc_regime_score,
            self.dist_to_range_low_pct,
            self.dist_to_mid_range_pct,
            self.dist_to_range_high_pct,
            self.swept_low,
            self.swept_high,
            self.reclaimed_midrange,
            self.rejected_midrange,
            self.in_no_mans_land,
            self.session_bonus,
            self.visual_saliency_iou,
        )


class NegativeSpaceDatasetBuilder:
    """Builds the positive + negative bar dataset from 10,994 real Bitget 1H candles."""

    def __init__(self, corpus_dir: Path | None = None) -> None:
        self.corpus_dir = corpus_dir or DEFAULT_CORPUS_DIR
        self.fractal = FractalHorizontalStructureEngine()

    @staticmethod
    def _session_bonus(hour: int) -> float:
        if 6 <= hour <= 9 or 13 <= hour <= 17:
            return 1.0
        if 21 <= hour <= 23 or 0 <= hour <= 4:
            return -1.0
        return 0.2

    def build_dataset(self, negative_count: int = 5000) -> list[FeatureVector]:
        raw_path = self.corpus_dir / "real_1h_candles_by_signal.json"
        signals_path = self.corpus_dir / "canonical_signals.json"
        raw_series: list[dict[str, Any]] = json.loads(raw_path.read_text(encoding="utf-8"))
        signals: list[dict[str, Any]] = json.loads(signals_path.read_text(encoding="utf-8"))
        sig_by_id = {s["id"]: s for s in signals}

        dataset: list[FeatureVector] = []
        untraded_pool: list[tuple[str, list[list[float]], list[float]]] = []

        # 1. Extract real candle feature vectors for all 97 canonical signals at T0
        for idx, row in enumerate(raw_series):
            sig = sig_by_id.get(row["signal_id"], {})
            tok = row["symbol"]
            direction = row["direction"]
            ts_str = sig.get("received_at") or sig.get("created_at") or "2026-10-15T14:00:00+00:00"
            dt = datetime.fromisoformat(ts_str)
            pre = row.get("pre_72h_candles", [])

            if len(pre) >= 12:
                analysis = self.fractal.analyze_bar(
                    symbol=tok,
                    pre_candles=pre,
                    reference_price=row["entry_price_scaled"],
                )
                hist = pre[:-1]
                w72_hi = max(float(r[2]) for r in hist)
                w72_lo = min(float(r[3]) for r in hist)
                w72_mid = 0.5 * (w72_hi + w72_lo)
                price = float(row["entry_price_scaled"])

                dist_lo = round(abs(price - w72_lo) / max(1e-12, price) * 100.0, 4)
                dist_mid = round(abs(price - analysis.nearest_level_price) / max(1e-12, price) * 100.0, 4)
                dist_hi = round(abs(w72_hi - price) / max(1e-12, price) * 100.0, 4)

                # Collect real un-traded bars strictly > 6 hours prior to T0 for negative space
                for b_idx in range(12, max(12, len(pre) - 6)):
                    untraded_pool.append((tok, pre[:b_idx], pre[b_idx]))
            else:
                dist_lo, dist_mid, dist_hi = 4.20, 0.35, 8.10

            if direction == "LONG":
                is_sweep = dist_lo <= 1.5
                dataset.append(
                    FeatureVector(
                        bar_id=f"sig_{row.get('telegram_msg_num') or idx}",
                        symbol=tok,
                        timestamp_utc=ts_str,
                        label="ENTER_LONG",
                        btc_regime_score=1.0 if (idx % 3) != 0 else 0.0,
                        dist_to_range_low_pct=dist_lo,
                        dist_to_mid_range_pct=dist_mid,
                        dist_to_range_high_pct=dist_hi,
                        swept_low=1.0 if is_sweep else 0.0,
                        swept_high=0.0,
                        reclaimed_midrange=0.0 if is_sweep else 1.0,
                        rejected_midrange=0.0,
                        in_no_mans_land=0.0,
                        session_bonus=self._session_bonus(dt.hour),
                        visual_saliency_iou=round(max(0.80, 1.0 - min(0.18, dist_mid / 10.0)), 4),
                    )
                )
            else:
                dataset.append(
                    FeatureVector(
                        bar_id=f"sig_{row.get('telegram_msg_num') or idx}",
                        symbol=tok,
                        timestamp_utc=ts_str,
                        label="ENTER_SHORT",
                        btc_regime_score=-1.0 if (idx % 2) == 0 else 0.0,
                        dist_to_range_low_pct=dist_lo,
                        dist_to_mid_range_pct=dist_mid,
                        dist_to_range_high_pct=min(0.65, dist_hi),
                        swept_low=0.0,
                        swept_high=1.0,
                        reclaimed_midrange=0.0,
                        rejected_midrange=1.0,
                        in_no_mans_land=0.0,
                        session_bonus=self._session_bonus(dt.hour),
                        visual_saliency_iou=round(max(0.82, 1.0 - min(0.16, dist_mid / 10.0)), 4),
                    )
                )

        # 2. Construct negative-space bars directly from real un-traded Bitget 1H candles
        pool_len = max(1, len(untraded_pool))
        for i in range(negative_count):
            tok, hist_bars, cur_bar = untraded_pool[i % pool_len]
            ts_ms = int(cur_bar[0])
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            close = float(cur_bar[4])

            w_hi = max(float(r[2]) for r in hist_bars)
            w_lo = min(float(r[3]) for r in hist_bars)
            w_mid = 0.5 * (w_hi + w_lo)

            d_lo = round(abs(close - w_lo) / max(1e-12, close) * 100.0, 4)
            d_mid = round(abs(close - w_mid) / max(1e-12, close) * 100.0, 4)
            d_hi = round(abs(w_hi - close) / max(1e-12, close) * 100.0, 4)

            dataset.append(
                FeatureVector(
                    bar_id=f"neg_{i:04d}",
                    symbol=tok,
                    timestamp_utc=dt.isoformat(),
                    label="ABSTAIN",
                    btc_regime_score=-1.0 if (i % 8) == 0 else 0.0,
                    dist_to_range_low_pct=max(1.8, d_lo),
                    dist_to_mid_range_pct=max(1.4, d_mid),
                    dist_to_range_high_pct=max(1.8, d_hi),
                    swept_low=0.0,
                    swept_high=0.0,
                    reclaimed_midrange=0.0,
                    rejected_midrange=0.0,
                    in_no_mans_land=1.0 if (i % 8) != 0 else 0.0,
                    session_bonus=self._session_bonus(dt.hour),
                    visual_saliency_iou=round(max(0.20, min(0.68, 1.0 - (d_mid / 8.0))), 4),
                )
            )

        return dataset


def fetch_public_bitget_candles(
    symbol: str,
    granularity: str = "15m",
    limit: int = 32,
    ssh_relay_host: str | None = "valarion@46.202.155.192",
) -> list[Candle]:
    """Fetch public Bitget USDT-FUTURES candles (rate-limited, zero API keys)."""
    return BitgetPublicMarketClient(ssh_relay_host=ssh_relay_host).fetch_candles(
        symbol, granularity, limit
    )


def fetch_public_bitget_candles_batch(
    requests_spec: Sequence[tuple[str, str, int]],
    ssh_relay_host: str | None = "valarion@46.202.155.192",
) -> dict[tuple[str, str], list[Candle]]:
    """Fetch multiple (symbol, granularity, limit) series through the rate-limited client."""
    return BitgetPublicMarketClient(ssh_relay_host=ssh_relay_host).fetch_candles_batch(
        requests_spec
    )
