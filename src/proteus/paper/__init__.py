"""Autonomous Virtual Paper Exchange (`proteus.paper`).

Maintains an air-gapped virtual paper-trading ledger (`benchmarks/paper_ledger.json`)
that ingests live `LiveShadowSnapshot` signals, opens virtual positions with 2.0%
capital risk per trade ($20.00 per 1.0R on a $1,000.00 synthetic equity base), and
steps active positions through `TradeLifecycleFSM` on every live market scan.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from proteus.domain.models import Direction, OrderMode, SetupArchetype, TradeSetup, TradeState
from proteus.fsm import TradeLifecycleFSM
from proteus.shadow import LiveShadowSnapshot

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[3] / "benchmarks" / "paper_ledger.json"


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
    opened_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True)
class VirtualPaperLedger:
    starting_equity_usdt: float
    risk_per_trade_usdt: float
    current_equity_usdt: float
    realized_pnl_usdt: float
    unrealized_pnl_usdt: float
    open_positions_count: int
    closed_positions_count: int
    positions: dict[str, VirtualPaperPosition]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class VirtualPaperExchange:
    """Steps virtual positions through `TradeLifecycleFSM` on live shadow scans."""

    def __init__(
        self,
        ledger_path: Path | None = None,
        starting_equity_usdt: float = 1000.0,
        risk_per_trade_usdt: float = 20.0,
    ) -> None:
        self.ledger_path = ledger_path or DEFAULT_LEDGER_PATH
        self.starting_equity_usdt = starting_equity_usdt
        self.risk_per_trade_usdt = risk_per_trade_usdt
        self.fsm = TradeLifecycleFSM()

    def process_shadow_snapshot(self, snapshot: LiveShadowSnapshot) -> VirtualPaperLedger:
        existing: dict[str, VirtualPaperPosition] = {}
        if self.ledger_path.exists():
            raw = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            for sym, pos_dict in raw.get("positions", {}).items():
                existing[sym] = VirtualPaperPosition(**pos_dict)

        scan_dt = datetime.fromisoformat(snapshot.scanned_at_utc)

        for asset in snapshot.states:
            sym = asset.symbol
            mark = Decimal(asset.last_close)

            # 1. Step any active position for this symbol through TradeLifecycleFSM
            if sym in existing and existing[sym].state not in (
                TradeState.CLOSED_TP.value,
                TradeState.CLOSED_SL.value,
                TradeState.CLOSED_EARLY.value,
            ):
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
                    confidence=0.86,
                    archetype=SetupArchetype(cur.archetype),
                )
                pos_state = self.fsm.open_position(
                    setup, datetime.fromisoformat(cur.opened_at_utc)
                )
                pos_state = self.fsm.on_tick(pos_state, mark, scan_dt)
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
                    opened_at_utc=cur.opened_at_utc,
                    updated_at_utc=snapshot.scanned_at_utc,
                )

            # 2. Admit new shadow signals if no active position exists for symbol
            elif asset.action in ("ENTER_LONG", "ENTER_SHORT") and asset.synthesized_sl and asset.synthesized_tp:
                direction = "LONG" if asset.action == "ENTER_LONG" else "SHORT"
                existing[sym] = VirtualPaperPosition(
                    symbol=sym,
                    direction=direction,
                    order_mode=asset.order_mode or "LIMIT",
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
                    opened_at_utc=snapshot.scanned_at_utc,
                    updated_at_utc=snapshot.scanned_at_utc,
                )

        realized_r_sum = sum(float(p.realized_r) for p in existing.values())
        unrealized_r_sum = sum(
            float(p.unrealized_r) * float(p.remaining_size_fraction)
            for p in existing.values()
            if p.state not in (
                TradeState.CLOSED_TP.value,
                TradeState.CLOSED_SL.value,
                TradeState.CLOSED_EARLY.value,
            )
        )
        realized_usdt = round(realized_r_sum * self.risk_per_trade_usdt, 2)
        unrealized_usdt = round(unrealized_r_sum * self.risk_per_trade_usdt, 2)
        current_eq = round(self.starting_equity_usdt + realized_usdt + unrealized_usdt, 2)

        open_cnt = sum(
            1
            for p in existing.values()
            if p.state
            not in (
                TradeState.CLOSED_TP.value,
                TradeState.CLOSED_SL.value,
                TradeState.CLOSED_EARLY.value,
            )
        )
        closed_cnt = len(existing) - open_cnt

        ledger = VirtualPaperLedger(
            starting_equity_usdt=self.starting_equity_usdt,
            risk_per_trade_usdt=self.risk_per_trade_usdt,
            current_equity_usdt=current_eq,
            realized_pnl_usdt=realized_usdt,
            unrealized_pnl_usdt=unrealized_usdt,
            open_positions_count=open_cnt,
            closed_positions_count=closed_cnt,
            positions=existing,
        )
        self.ledger_path.write_text(json.dumps(ledger.to_dict(), indent=2) + "\n", encoding="utf-8")
        return ledger

    def run_historical_paper_simulation(self) -> dict[str, object]:
        """Simulate a $1,000 USDT paper account across all 97 historical signals."""
        from proteus.backtest import LifecycleBacktestSimulator

        sim = LifecycleBacktestSimulator()
        bt = sim.run_comparative_backtest()

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
            "proteus_distilled_clone": {
                "ending_equity_usdt": round(
                    self.starting_equity_usdt + proteus_pnl_usdt, 2
                ),
                "net_profit_usdt": proteus_pnl_usdt,
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
