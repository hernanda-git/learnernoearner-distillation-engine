"""Module 7: In-Flight Trade Management FSM (`proteus.fsm`).

Models the trader's post-entry behavioral habits:
1. +1.0R Breakeven migration (`sl to entry`)
2. Circadian bedtime derisking (UTC 21:00+ profit locking)
3. Linguistic update translation (`tp1 booked`, `full tp booked`, `sl to entry`)
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from proteus.domain.models import Direction, PositionState, TradeSetup, TradeState


class TradeLifecycleFSM:
    """Deterministic finite-state machine for active trade lifecycle management."""

    BREAKEVEN_TRIGGER_R: Decimal = Decimal("1.00")
    BEDTIME_START_HOUR_UTC: int = 21
    BEDTIME_END_HOUR_UTC: int = 23

    def open_position(self, setup: TradeSetup, opened_at_utc: datetime) -> PositionState:
        return PositionState(
            setup=setup,
            state=TradeState.ACTIVE,
            current_sl=setup.stop_loss,
            current_tp=setup.take_profit,
            remaining_size_fraction=Decimal("1.00"),
            realized_r=Decimal("0.00"),
            unrealized_r=Decimal("0.00"),
            opened_at_utc=opened_at_utc,
            updated_at_utc=opened_at_utc,
        )

    @staticmethod
    def compute_r_multiple(setup: TradeSetup, mark_price: Decimal) -> Decimal:
        initial_risk = abs(setup.entry_price - setup.stop_loss)
        if initial_risk <= Decimal("0"):
            return Decimal("0.00")
        if setup.direction == Direction.LONG:
            pnl = mark_price - setup.entry_price
        else:
            pnl = setup.entry_price - mark_price
        return (pnl / initial_risk).quantize(Decimal("0.01"))

    def on_tick(
        self,
        position: PositionState,
        mark_price: Decimal,
        timestamp_utc: datetime,
    ) -> PositionState:
        if position.state in (
            TradeState.CLOSED_TP,
            TradeState.CLOSED_SL,
            TradeState.CLOSED_EARLY,
        ):
            return position

        setup = position.setup
        r_mult = self.compute_r_multiple(setup, mark_price)

        # 1. Check Stop-Loss / Breakeven stop breach
        sl_hit = (
            mark_price <= position.current_sl
            if setup.direction == Direction.LONG
            else mark_price >= position.current_sl
        )
        if sl_hit:
            locked_r = self.compute_r_multiple(setup, position.current_sl)
            total_realized = (
                position.realized_r + locked_r * position.remaining_size_fraction
            ).quantize(Decimal("0.01"))
            return replace(
                position,
                state=TradeState.CLOSED_SL,
                remaining_size_fraction=Decimal("0.00"),
                realized_r=total_realized,
                unrealized_r=Decimal("0.00"),
                updated_at_utc=timestamp_utc,
            )

        # 2. Check Full Take-Profit target hit
        tp_hit = (
            mark_price >= position.current_tp
            if setup.direction == Direction.LONG
            else mark_price <= position.current_tp
        )
        if tp_hit:
            target_r = self.compute_r_multiple(setup, position.current_tp)
            total_realized = (
                position.realized_r + target_r * position.remaining_size_fraction
            ).quantize(Decimal("0.01"))
            return replace(
                position,
                state=TradeState.CLOSED_TP,
                remaining_size_fraction=Decimal("0.00"),
                realized_r=total_realized,
                unrealized_r=Decimal("0.00"),
                updated_at_utc=timestamp_utc,
            )

        next_state = position.state
        next_sl = position.current_sl
        next_remaining = position.remaining_size_fraction
        next_realized = position.realized_r

        # 3. Rule 1: +1.0R Breakeven Migration ("sl to entry")
        if r_mult >= self.BREAKEVEN_TRIGGER_R and next_state == TradeState.ACTIVE:
            next_state = TradeState.BREAKEVEN_PROTECTED
            next_sl = setup.entry_price

        # 4. Rule 2: Circadian Bedtime Derisking (UTC 21:00-23:59)
        if (
            self.BEDTIME_START_HOUR_UTC <= timestamp_utc.hour <= self.BEDTIME_END_HOUR_UTC
            and r_mult > Decimal("0.00")
            and next_state not in (TradeState.BEDTIME_DERISKED, TradeState.CLOSED_EARLY)
        ):
            if r_mult >= self.BREAKEVEN_TRIGGER_R:
                closed_fraction = (next_remaining * Decimal("0.50")).quantize(Decimal("0.01"))
                next_realized = (next_realized + r_mult * closed_fraction).quantize(Decimal("0.01"))
                next_remaining = (next_remaining - closed_fraction).quantize(Decimal("0.01"))
                next_sl = setup.entry_price
                next_state = TradeState.BEDTIME_DERISKED
            else:
                total_realized = (next_realized + r_mult * next_remaining).quantize(Decimal("0.01"))
                return replace(
                    position,
                    state=TradeState.CLOSED_EARLY,
                    remaining_size_fraction=Decimal("0.00"),
                    realized_r=total_realized,
                    unrealized_r=Decimal("0.00"),
                    updated_at_utc=timestamp_utc,
                )

        return replace(
            position,
            state=next_state,
            current_sl=next_sl,
            remaining_size_fraction=next_remaining,
            realized_r=next_realized,
            unrealized_r=r_mult,
            updated_at_utc=timestamp_utc,
        )

    def apply_linguistic_command(
        self,
        position: PositionState,
        message_text: str,
        timestamp_utc: datetime,
    ) -> PositionState:
        """Translate canonical Telegram trade management phrases into FSM transitions."""
        normalized = " ".join(message_text.lower().strip().split())

        if "sl to entry" in normalized or "stoploss to entry" in normalized:
            return replace(
                position,
                state=TradeState.BREAKEVEN_PROTECTED,
                current_sl=position.setup.entry_price,
                updated_at_utc=timestamp_utc,
            )

        if "tp1 booked" in normalized:
            half = (position.remaining_size_fraction * Decimal("0.50")).quantize(Decimal("0.01"))
            booked_r = max(Decimal("1.00"), position.unrealized_r)
            return replace(
                position,
                state=TradeState.PARTIAL_TP_BOOKED,
                current_sl=position.setup.entry_price,
                remaining_size_fraction=position.remaining_size_fraction - half,
                realized_r=(position.realized_r + booked_r * half).quantize(Decimal("0.01")),
                updated_at_utc=timestamp_utc,
            )

        if "full tp booked" in normalized:
            booked_r = max(position.setup.planned_rr, position.unrealized_r)
            total_r = (
                position.realized_r + booked_r * position.remaining_size_fraction
            ).quantize(Decimal("0.01"))
            return replace(
                position,
                state=TradeState.CLOSED_TP,
                remaining_size_fraction=Decimal("0.00"),
                realized_r=total_r,
                unrealized_r=Decimal("0.00"),
                updated_at_utc=timestamp_utc,
            )

        if "closed" in normalized and "profit" in normalized:
            total_r = (
                position.realized_r + position.unrealized_r * position.remaining_size_fraction
            ).quantize(Decimal("0.01"))
            return replace(
                position,
                state=TradeState.CLOSED_EARLY,
                remaining_size_fraction=Decimal("0.00"),
                realized_r=total_r,
                unrealized_r=Decimal("0.00"),
                updated_at_utc=timestamp_utc,
            )

        return position
