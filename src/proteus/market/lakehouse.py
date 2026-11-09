"""Phase 1: Real-candle negative-space lakehouse (`proteus.market.lakehouse`).

Every feature is computed from the pre-entry candle window only. There is no
label-derived or index-derived value: positives and negatives are built by the
same `_extract_features` function, so a classifier cannot separate classes by
construction.

Signals without a Bitget 1H series (delisted or missing) are excluded from the
labeled dataset; they remain in the corpus with an explicit manifest entry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from proteus.domain.models import Candle
from proteus.market.bitget import BitgetPublicMarketClient

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "corpus"

# Match `StructuralGeometryEngine` defaults so the lakehouse and the live path
# describe the same structure.
LEVEL_PROXIMITY_PCT = 0.012
SWEEP_PROXIMITY_PCT = 0.006
WICK_REJECTION_THRESHOLD = 0.35


@dataclass(frozen=True)
class FeatureVector:
    bar_id: str
    symbol: str
    timestamp_utc: str
    label: str  # "ABSTAIN", "ENTER_LONG", "ENTER_SHORT"
    dist_to_range_low_pct: float
    dist_to_mid_range_pct: float
    dist_to_range_high_pct: float
    swept_low: float
    swept_high: float
    reclaimed_midrange: float
    rejected_midrange: float
    in_no_mans_land: float
    session_bonus: float

    def to_numeric_tuple(self) -> tuple[float, ...]:
        return (
            self.dist_to_range_low_pct,
            self.dist_to_mid_range_pct,
            self.dist_to_range_high_pct,
            self.swept_low,
            self.swept_high,
            self.reclaimed_midrange,
            self.rejected_midrange,
            self.in_no_mans_land,
            self.session_bonus,
        )


class NegativeSpaceDatasetBuilder:
    """Builds the positive + negative bar dataset from the real 1H candles."""

    def __init__(self, corpus_dir: Path | None = None) -> None:
        self.corpus_dir = corpus_dir or DEFAULT_CORPUS_DIR

    @staticmethod
    def _session_bonus(hour: int) -> float:
        if 6 <= hour <= 9 or 13 <= hour <= 17:
            return 1.0
        if 21 <= hour <= 23 or 0 <= hour <= 4:
            return -1.0
        return 0.2

    @staticmethod
    def _extract_features(pre: Sequence[Sequence[float]], dt: datetime) -> dict[str, float]:
        """Compute structural features from raw OHLCV bars, with zero label input.

        `pre` is the sequence ending at the trigger bar. The range is measured on
        `pre[:-1]`; the trigger is `pre[-1]`, exactly like the zero-lookahead
        fractal engine.
        """
        hist = list(pre[:-1]) if len(pre) > 1 else list(pre)
        cur = pre[-1]

        w_hi = max(float(r[2]) for r in hist)
        w_lo = min(float(r[3]) for r in hist)
        mid = 0.5 * (w_hi + w_lo)

        o, h, l, c = float(cur[1]), float(cur[2]), float(cur[3]), float(cur[4])
        price = c
        rng = max(1e-12, h - l)
        body_low = min(o, c)
        body_high = max(o, c)
        lower_wick = (body_low - l) / rng
        upper_wick = (h - body_high) / rng

        dist_lo = abs(price - w_lo) / max(1e-12, price) * 100.0
        dist_mid = abs(price - mid) / max(1e-12, price) * 100.0
        dist_hi = abs(w_hi - price) / max(1e-12, price) * 100.0

        swept_low = (
            l <= w_lo * (1.0 + SWEEP_PROXIMITY_PCT)
            and c > w_lo
            and (lower_wick >= WICK_REJECTION_THRESHOLD or c > o)
        )
        swept_high = (
            h >= w_hi * (1.0 - SWEEP_PROXIMITY_PCT)
            and c < w_hi
            and (upper_wick >= WICK_REJECTION_THRESHOLD or c < o)
        )
        reclaimed_mid = (
            c >= mid
            and (
                abs(l - mid) / max(1e-12, mid) <= LEVEL_PROXIMITY_PCT
                or abs(c - mid) / max(1e-12, mid) <= LEVEL_PROXIMITY_PCT
            )
            and l <= mid * (1.0 + LEVEL_PROXIMITY_PCT)
        )
        rejected_mid = (
            c < mid
            and (
                abs(h - mid) / max(1e-12, mid) <= LEVEL_PROXIMITY_PCT
                or abs(c - mid) / max(1e-12, mid) <= LEVEL_PROXIMITY_PCT
            )
            and h >= mid * (1.0 - LEVEL_PROXIMITY_PCT)
        )

        near_lo = abs(c - w_lo) / max(1e-12, w_lo) <= LEVEL_PROXIMITY_PCT
        near_hi = abs(c - w_hi) / max(1e-12, w_hi) <= LEVEL_PROXIMITY_PCT
        near_mid = abs(c - mid) / max(1e-12, mid) <= LEVEL_PROXIMITY_PCT
        in_no_mans_land = not (
            swept_low or swept_high or reclaimed_mid or rejected_mid or near_lo or near_hi or near_mid
        )

        return {
            "dist_to_range_low_pct": round(dist_lo, 4),
            "dist_to_mid_range_pct": round(dist_mid, 4),
            "dist_to_range_high_pct": round(dist_hi, 4),
            "swept_low": 1.0 if swept_low else 0.0,
            "swept_high": 1.0 if swept_high else 0.0,
            "reclaimed_midrange": 1.0 if reclaimed_mid else 0.0,
            "rejected_midrange": 1.0 if rejected_mid else 0.0,
            "in_no_mans_land": 1.0 if in_no_mans_land else 0.0,
            "session_bonus": NegativeSpaceDatasetBuilder._session_bonus(dt.hour),
        }

    def build_dataset(self, negative_count: int = 5000) -> list[FeatureVector]:
        raw_path = self.corpus_dir / "real_1h_candles_by_signal.json"
        signals_path = self.corpus_dir / "canonical_signals.json"
        raw_series: list[dict[str, Any]] = json.loads(raw_path.read_text(encoding="utf-8"))
        signals: list[dict[str, Any]] = json.loads(signals_path.read_text(encoding="utf-8"))
        sig_by_id = {s["id"]: s for s in signals if s.get("telegram_msg_num") != 999999999}

        dataset: list[FeatureVector] = []
        untraded_pool: list[tuple[str, list[list[float]]]] = []
        seen_pool: set[tuple[str, int]] = set()

        for idx, row in enumerate(raw_series):
            sig = sig_by_id.get(row["signal_id"])
            pre = row.get("pre_72h_candles") or []
            if sig is None or len(pre) < 12:
                continue

            tok = row["symbol"]
            direction = sig["direction"]
            ts_str = sig.get("received_at") or sig.get("created_at")
            dt = datetime.fromisoformat(ts_str)
            features = self._extract_features(pre, dt)

            dataset.append(
                FeatureVector(
                    bar_id=f"sig_{row.get('telegram_msg_num') or idx}",
                    symbol=tok,
                    timestamp_utc=ts_str,
                    label="ENTER_LONG" if direction == "LONG" else "ENTER_SHORT",
                    **features,
                )
            )

            # Un-traded bars strictly more than 6 hours before T0.
            for b_idx in range(12, max(12, len(pre) - 6)):
                key = (tok, int(pre[b_idx][0]))
                if key in seen_pool:
                    continue
                seen_pool.add(key)
                untraded_pool.append((tok, pre[: b_idx + 1]))

        if not untraded_pool:
            return dataset

        for i in range(negative_count):
            tok, window = untraded_pool[i % len(untraded_pool)]
            ts_ms = int(window[-1][0])
            dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            features = self._extract_features(window, dt)
            dataset.append(
                FeatureVector(
                    bar_id=f"neg_{i:04d}",
                    symbol=tok,
                    timestamp_utc=dt.isoformat(),
                    label="ABSTAIN",
                    **features,
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
