"""Portfolio bookkeeping for a single-instrument backtest.

The portfolio is always either flat or fully invested (long or short) using all
available equity. This keeps the simulation simple and deterministic while
still producing a realistic equity curve and trade log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TradeRecord:
    """A completed (or open) round-trip trade."""

    side: str  # "long" or "short"
    quantity: float
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    pnl: float | None = None

    @property
    def is_open(self) -> bool:
        return self.exit_time is None


@dataclass
class Portfolio:
    """Tracks cash, the open position, the equity curve and closed trades."""

    initial_capital: float
    cash: float = field(init=False)
    # Signed position size in units: positive = long, negative = short.
    position: float = 0.0
    _open_trade: TradeRecord | None = field(default=None, init=False)
    trades: list[TradeRecord] = field(default_factory=list, init=False)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.cash = float(self.initial_capital)

    @property
    def side(self) -> int:
        if self.position > 0:
            return 1
        if self.position < 0:
            return -1
        return 0

    def equity(self, price: float) -> float:
        """Mark-to-market account value at ``price``."""
        return self.cash + self.position * price

    def open_position(self, target: int, price: float, when: datetime) -> None:
        """Open a fully invested long (target=1) or short (target=-1)."""
        if target == 0 or price <= 0:
            return
        notional = self.equity(price)
        quantity = notional / price
        self.position = quantity * target
        # Cash falls by the cost of a long, rises by the proceeds of a short.
        self.cash -= self.position * price
        self._open_trade = TradeRecord(
            side="long" if target > 0 else "short",
            quantity=quantity,
            entry_time=when,
            entry_price=price,
        )

    def close_position(self, price: float, when: datetime) -> None:
        """Liquidate the open position at ``price`` and record the trade."""
        if self.position == 0 or self._open_trade is None:
            return
        self.cash += self.position * price
        trade = self._open_trade
        trade.exit_time = when
        trade.exit_price = price
        # PnL on the signed position: gains when price moves in our favour.
        trade.pnl = (price - trade.entry_price) * self.position
        self.trades.append(trade)
        self.position = 0.0
        self._open_trade = None

    def mark(self, price: float, when: datetime) -> None:
        """Append the current equity to the curve."""
        self.equity_curve.append((when, self.equity(price)))
