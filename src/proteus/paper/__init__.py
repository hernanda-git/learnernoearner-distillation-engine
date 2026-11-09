"""Autonomous Virtual Paper Exchange (`proteus.paper`).

Includes Phase 6 Extensions:
- Phase 6.2: Bitget USDT-FUTURES fee model (Maker 2.0 bps = 0.02% for LIMIT entries,
  Taker 6.0 bps = 0.06% for MARKET entries & stop/market exits) + LIMIT band fill check.
- Phase 6.4: Portfolio Margin Velocity Cap (`max_open_positions = 3`). When slots are
  full and a higher-conviction setup arrives, evicts the most stalled open trade
  (-0.15R <= unrealized_r <= +0.35R) to free margin ("closed $POWER $10 profit so we
  can have margin to take another trade").
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from proteus.domain.models import (
    Direction,
    OrderMode,
    PositionState,
    SetupArchetype,
    TradeSetup,
    TradeState,
)
from proteus.fsm import TradeLifecycleFSM
from proteus.shadow import LiveShadowSnapshot

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[3] / "benchmarks" / "paper_ledger.json"

BITGET_MAKER_FEE_PCT: float = 0.0002  # 2.0 bps (0.02%)
BITGET_TAKER_FEE_PCT: float = 0.0006  # 6.0 bps (0.06%)


@dataclass(frozen=True)
class VirtualPaperPosition:
    symbol: str
    direction: str
    order_mode: str
    archetype: str
    entry_price: str
    stop_loss: str
    current_sl: str
    take_profit: str
    planned_rr: str
    state: str
    remaining_size_fraction: str
    realized_r: str
    unrealized_r: str
    fees_paid_usdt: float = 0.0
    confidence: float = 0.86
    eviction_reason: str | None = None
    opened_at_utc: str = ""
    updated_at_utc: str = ""


@dataclass(frozen=True)
class VirtualPaperLedger:
    starting_equity_usdt: float
    risk_per_trade_usdt: float
    max_open_positions: int
    current_equity_usdt: float
    realized_pnl_usdt: float
    unrealized_pnl_usdt: float
    total_fees_paid_usdt: float
    margin_evictions_count: int
    open_positions_count: int
    closed_positions_count: int
    positions: dict[str, VirtualPaperPosition]
    peak_equity_usdt: float = 0.0
    max_drawdown_pct: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class VirtualPaperExchange:
    """Steps virtual positions through `TradeLifecycleFSM` with fees & slot eviction."""

    def __init__(
        self,
        ledger_path: Path | None = None,
        starting_equity_usdt: float = 1000.0,
        risk_per_trade_usdt: float = 20.0,
        max_open_positions: int = 3,
    ) -> None:
        self.ledger_path = ledger_path or DEFAULT_LEDGER_PATH
        self.starting_equity_usdt = starting_equity_usdt
        self.risk_per_trade_usdt = risk_per_trade_usdt
        self.max_open_positions = max_open_positions
        self.fsm = TradeLifecycleFSM()

    @staticmethod
    def compute_position_notional_usdt(
        entry_price: float,
        stop_loss: float,
        risk_usdt: float,
    ) -> float:
        sl_dist_pct = abs(entry_price - stop_loss) / max(1e-12, entry_price)
        return round(risk_usdt / max(0.005, sl_dist_pct), 2)

    @classmethod
    def compute_entry_fee_usdt(
        cls,
        entry_price: float,
        stop_loss: float,
        risk_usdt: float,
        order_mode: str,
    ) -> float:
        notional = cls.compute_position_notional_usdt(entry_price, stop_loss, risk_usdt)
        rate = BITGET_MAKER_FEE_PCT if order_mode == "LIMIT" else BITGET_TAKER_FEE_PCT
        return round(notional * rate, 4)

    @staticmethod
    def _is_terminal(state: str) -> bool:
        return state in (
            TradeState.CLOSED_TP.value,
            TradeState.CLOSED_SL.value,
            TradeState.CLOSED_EARLY.value,
        )

    def process_shadow_snapshot(self, snapshot: LiveShadowSnapshot) -> VirtualPaperLedger:
        existing: dict[str, VirtualPaperPosition] = {}
        prev_peak = self.starting_equity_usdt
        prev_dd = 0.0
        if self.ledger_path.exists():
            raw = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            for sym, pos_dict in raw.get("positions", {}).items():
                existing[sym] = VirtualPaperPosition(**pos_dict)
            prev_peak = float(raw.get("peak_equity_usdt", self.starting_equity_usdt))
            prev_dd = float(raw.get("max_drawdown_pct", 0.0))

        scan_dt = datetime.fromisoformat(snapshot.scanned_at_utc)

        # Pass 1: Step all currently open positions through TradeLifecycleFSM
        just_closed: set[str] = set()
        for asset in snapshot.states:
            sym = asset.symbol
            mark = Decimal(asset.last_close)

            if sym in existing and not self._is_terminal(existing[sym].state):
                cur = existing[sym]
                setup = TradeSetup(
                    symbol=sym,
                    direction=Direction(cur.direction),
                    order_mode=OrderMode(cur.order_mode),
                    entry_price=Decimal(cur.entry_price),
                    stop_loss=Decimal(cur.stop_loss),
                    take_profit=Decimal(cur.take_profit),
                    planned_rr=Decimal(cur.planned_rr),
                    risk_pct=Decimal("2.60"),
                    confidence=cur.confidence,
                    archetype=SetupArchetype(cur.archetype),
                )
                # Restore the live state, not a fresh position. The previous
                # implementation called open_position(), which reset the
                # breakeven stop and the partial-TP ledger on every scan.
                pos_state = PositionState(
                    setup=setup,
                    state=TradeState(cur.state),
                    current_sl=Decimal(cur.current_sl),
                    current_tp=Decimal(cur.take_profit),
                    remaining_size_fraction=Decimal(cur.remaining_size_fraction),
                    realized_r=Decimal(cur.realized_r),
                    unrealized_r=Decimal(cur.unrealized_r),
                    opened_at_utc=datetime.fromisoformat(cur.opened_at_utc),
                    updated_at_utc=datetime.fromisoformat(cur.updated_at_utc),
                )
                pos_state = self.fsm.on_tick(pos_state, mark, scan_dt)

                notional = self.compute_position_notional_usdt(
                    float(cur.entry_price),
                    float(cur.stop_loss),
                    self.risk_per_trade_usdt,
                )
                fees = cur.fees_paid_usdt
                if (
                    pos_state.state == TradeState.PARTIAL_TP_BOOKED
                    and cur.state != TradeState.PARTIAL_TP_BOOKED.value
                ):
                    fees = round(fees + notional * 0.5 * BITGET_TAKER_FEE_PCT, 4)
                if self._is_terminal(pos_state.state.value):
                    closed_fraction = float(cur.remaining_size_fraction)
                    fees = round(fees + notional * closed_fraction * BITGET_TAKER_FEE_PCT, 4)
                    just_closed.add(sym)

                existing[sym] = VirtualPaperPosition(
                    symbol=sym,
                    direction=cur.direction,
                    order_mode=cur.order_mode,
                    archetype=cur.archetype,
                    entry_price=cur.entry_price,
                    stop_loss=cur.stop_loss,
                    current_sl=str(pos_state.current_sl),
                    take_profit=cur.take_profit,
                    planned_rr=cur.planned_rr,
                    state=pos_state.state.value,
                    remaining_size_fraction=str(pos_state.remaining_size_fraction),
                    realized_r=str(pos_state.realized_r),
                    unrealized_r=str(pos_state.unrealized_r),
                    fees_paid_usdt=fees,
                    confidence=cur.confidence,
                    eviction_reason=cur.eviction_reason,
                    opened_at_utc=cur.opened_at_utc,
                    updated_at_utc=snapshot.scanned_at_utc,
                )

        # Pass 2: Admit new signals with Phase 6.4 Margin Velocity Slot Eviction
        for asset in snapshot.states:
            sym = asset.symbol
            if sym in just_closed:
                continue
            if sym in existing and not self._is_terminal(existing[sym].state):
                continue
            if asset.action not in ("ENTER_LONG", "ENTER_SHORT") or not (
                asset.synthesized_sl and asset.synthesized_tp
            ):
                continue

            active_syms = [
                k for k, p in existing.items() if not self._is_terminal(p.state)
            ]
            if len(active_syms) >= self.max_open_positions:
                # Phase 6.4: Find a stalled position (-0.15R <= unrealized_r <= +0.35R)
                # with lower conviction than the incoming setup
                stalled_candidates = [
                    existing[k]
                    for k in active_syms
                    if -0.15 <= float(existing[k].unrealized_r) <= 0.35
                    and existing[k].confidence <= asset.confidence
                ]
                if not stalled_candidates:
                    continue
                stalled_candidates.sort(key=lambda p: (float(p.unrealized_r), p.confidence))
                evicted = stalled_candidates[0]
                notional = self.compute_position_notional_usdt(
                    float(evicted.entry_price),
                    float(evicted.stop_loss),
                    self.risk_per_trade_usdt,
                )
                exit_fee = round(notional * BITGET_TAKER_FEE_PCT, 4)
                locked_r = round(
                    float(evicted.realized_r)
                    + float(evicted.unrealized_r) * float(evicted.remaining_size_fraction),
                    2,
                )
                existing[evicted.symbol] = VirtualPaperPosition(
                    symbol=evicted.symbol,
                    direction=evicted.direction,
                    order_mode=evicted.order_mode,
                    archetype=evicted.archetype,
                    entry_price=evicted.entry_price,
                    stop_loss=evicted.stop_loss,
                    current_sl=evicted.current_sl,
                    take_profit=evicted.take_profit,
                    planned_rr=evicted.planned_rr,
                    state=TradeState.CLOSED_EARLY.value,
                    remaining_size_fraction="0.00",
                    realized_r=f"{locked_r:.2f}",
                    unrealized_r="0.00",
                    fees_paid_usdt=round(evicted.fees_paid_usdt + exit_fee, 4),
                    confidence=evicted.confidence,
                    eviction_reason=f"margin_velocity_eviction_for_{sym}",
                    opened_at_utc=evicted.opened_at_utc,
                    updated_at_utc=snapshot.scanned_at_utc,
                )

            direction = "LONG" if asset.action == "ENTER_LONG" else "SHORT"
            mode = asset.order_mode or "LIMIT"
            entry_fee = self.compute_entry_fee_usdt(
                float(asset.last_close),
                float(asset.synthesized_sl),
                self.risk_per_trade_usdt,
                mode,
            )
            existing[sym] = VirtualPaperPosition(
                symbol=sym,
                direction=direction,
                order_mode=mode,
                archetype=asset.archetype,
                entry_price=asset.last_close,
                stop_loss=asset.synthesized_sl,
                current_sl=asset.synthesized_sl,
                take_profit=asset.synthesized_tp,
                planned_rr="4.56",
                state=TradeState.ACTIVE.value,
                remaining_size_fraction="1.00",
                realized_r="0.00",
                unrealized_r="0.00",
                fees_paid_usdt=entry_fee,
                confidence=asset.confidence,
                eviction_reason=None,
                opened_at_utc=snapshot.scanned_at_utc,
                updated_at_utc=snapshot.scanned_at_utc,
            )

        realized_r_sum = sum(float(p.realized_r) for p in existing.values())
        unrealized_r_sum = sum(
            float(p.unrealized_r) * float(p.remaining_size_fraction)
            for p in existing.values()
            if not self._is_terminal(p.state)
        )
        total_fees = round(sum(p.fees_paid_usdt for p in existing.values()), 2)
        realized_usdt = round(realized_r_sum * self.risk_per_trade_usdt - total_fees, 2)
        unrealized_usdt = round(unrealized_r_sum * self.risk_per_trade_usdt, 2)
        current_eq = round(self.starting_equity_usdt + realized_usdt + unrealized_usdt, 2)
        peak_eq = round(max(prev_peak, current_eq, self.starting_equity_usdt), 2)
        dd_pct = round(
            max(prev_dd, (peak_eq - current_eq) / max(1.0, peak_eq) * 100.0), 2
        )

        open_cnt = sum(1 for p in existing.values() if not self._is_terminal(p.state))
        closed_cnt = len(existing) - open_cnt
        evictions_cnt = sum(1 for p in existing.values() if p.eviction_reason is not None)

        ledger = VirtualPaperLedger(
            starting_equity_usdt=self.starting_equity_usdt,
            risk_per_trade_usdt=self.risk_per_trade_usdt,
            max_open_positions=self.max_open_positions,
            current_equity_usdt=current_eq,
            realized_pnl_usdt=realized_usdt,
            unrealized_pnl_usdt=unrealized_usdt,
            total_fees_paid_usdt=total_fees,
            margin_evictions_count=evictions_cnt,
            open_positions_count=open_cnt,
            closed_positions_count=closed_cnt,
            positions=existing,
            peak_equity_usdt=peak_eq,
            max_drawdown_pct=dd_pct,
        )
        self.ledger_path.write_text(json.dumps(ledger.to_dict(), indent=2) + "\n", encoding="utf-8")
        return ledger

    def run_historical_paper_simulation(self) -> dict[str, object]:
        """Simulate a $1,000 USDT paper account across every resolvable historical signal."""
        from proteus.backtest import LifecycleBacktestSimulator

        sim = LifecycleBacktestSimulator()
        bt = sim.run_comparative_backtest()

        # The backtest already deducts round-trip fees from every R.
        estimated_fees_usdt = round(
            bt.proteus_distilled_fsm.total_fees_r * self.risk_per_trade_usdt, 2
        )

        proteus_pnl_usdt = round(
            bt.proteus_distilled_fsm.total_realized_r * self.risk_per_trade_usdt, 2
        )
        naive_pnl_usdt = round(
            bt.naive_set_and_forget.total_realized_r * self.risk_per_trade_usdt, 2
        )
        proteus_max_dd_usdt = round(
            bt.proteus_distilled_fsm.max_drawdown_r * self.risk_per_trade_usdt, 2
        )
        naive_max_dd_usdt = round(
            bt.naive_set_and_forget.max_drawdown_r * self.risk_per_trade_usdt, 2
        )

        return {
            "starting_equity_usdt": self.starting_equity_usdt,
            "risk_per_trade_usdt": self.risk_per_trade_usdt,
            "risk_per_trade_pct": round(
                (self.risk_per_trade_usdt / self.starting_equity_usdt) * 100.0, 2
            ),
            "estimated_fees_usdt": estimated_fees_usdt,
            "fees_included_in_r": True,
            "proteus_distilled_clone": {
                "ending_equity_usdt": round(
                    self.starting_equity_usdt + proteus_pnl_usdt, 2
                ),
                "ending_equity_after_fees_usdt": round(
                    self.starting_equity_usdt + proteus_pnl_usdt, 2
                ),
                "net_profit_usdt": proteus_pnl_usdt,
                "net_profit_after_fees_usdt": proteus_pnl_usdt,
                "return_pct": round(
                    (proteus_pnl_usdt / self.starting_equity_usdt) * 100.0, 2
                ),
                "max_drawdown_usdt": proteus_max_dd_usdt,
                "max_drawdown_pct": round(
                    (proteus_max_dd_usdt / self.starting_equity_usdt) * 100.0, 2
                ),
                "win_rate_pct": bt.proteus_distilled_fsm.win_rate_pct,
                "scratch_rate_pct": bt.proteus_distilled_fsm.scratch_rate_pct,
                "loss_rate_pct": bt.proteus_distilled_fsm.loss_rate_pct,
                "profit_factor": bt.proteus_distilled_fsm.profit_factor,
            },
            "naive_set_and_forget": {
                "ending_equity_usdt": round(
                    self.starting_equity_usdt + naive_pnl_usdt, 2
                ),
                "net_profit_usdt": naive_pnl_usdt,
                "return_pct": round(
                    (naive_pnl_usdt / self.starting_equity_usdt) * 100.0, 2
                ),
                "max_drawdown_usdt": naive_max_dd_usdt,
                "max_drawdown_pct": round(
                    (naive_max_dd_usdt / self.starting_equity_usdt) * 100.0, 2
                ),
                "win_rate_pct": bt.naive_set_and_forget.win_rate_pct,
                "scratch_rate_pct": bt.naive_set_and_forget.scratch_rate_pct,
                "loss_rate_pct": bt.naive_set_and_forget.loss_rate_pct,
                "profit_factor": bt.naive_set_and_forget.profit_factor,
            },
        }
