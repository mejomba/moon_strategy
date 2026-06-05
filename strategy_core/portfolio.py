"""Portfolio bookkeeping for a single-instrument backtest.

The portfolio is always either flat or fully invested (long or short) using all
available equity. Every fill is executed through a
:class:`~strategy_core.costs.CostModel`, so commission, slippage, spread and
funding are reflected in the cash balance, the equity curve, and each trade's
net PnL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from strategy_core.costs import ZERO_COST, CostModel


@dataclass
class TradeRecord:
    """A completed (or open) round-trip trade, net of costs."""

    side: str  # "long" or "short"
    quantity: float
    entry_time: datetime
    entry_price: float  # actual fill price, including spread/slippage
    exit_time: datetime | None = None
    exit_price: float | None = None
    gross_pnl: float | None = None  # price PnL before costs
    commission: float = 0.0  # total commission paid (entry + exit)
    funding: float = 0.0  # net funding paid (positive) or received (negative)
    pnl: float | None = None  # net PnL = gross_pnl - commission - funding

    @property
    def is_open(self) -> bool:
        return self.exit_time is None


@dataclass
class Portfolio:
    """Tracks cash, the open position, the equity curve and closed trades."""

    initial_capital: float
    cost_model: CostModel = ZERO_COST
    cash: float = field(init=False)
    # Signed position size in units: positive = long, negative = short.
    position: float = 0.0
    _open_trade: TradeRecord | None = field(default=None, init=False)
    _funding_accrued: float = field(default=0.0, init=False)
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
        """Mark-to-market account value at the (mid) ``price``."""
        return self.cash + self.position * price

    def open_position(self, target: int, price: float, when: datetime) -> None:
        """Open a fully invested long (target=1) or short (target=-1)."""
        if target == 0 or price <= 0:
            return
        fill = self.cost_model.fill_price(price, target)
        quantity = self.equity(price) / fill
        self.position = quantity * target
        # Cash falls by the cost of a long, rises by the proceeds of a short.
        self.cash -= self.position * fill
        commission = self.cost_model.commission(self.position * fill)
        self.cash -= commission
        self._funding_accrued = 0.0
        self._open_trade = TradeRecord(
            side="long" if target > 0 else "short",
            quantity=quantity,
            entry_time=when,
            entry_price=fill,
            commission=commission,
        )

    def accrue_funding(self, price: float, hours: float) -> None:
        """Charge (or credit) funding for holding the position for ``hours``."""
        if self.position == 0:
            return
        funding = self.cost_model.funding(self.position * price, self.side, hours)
        self.cash -= funding
        self._funding_accrued += funding

    def close_position(self, price: float, when: datetime) -> None:
        """Liquidate the open position at ``price`` and record the trade."""
        if self.position == 0 or self._open_trade is None:
            return
        closing_direction = -self.side  # selling a long, buying back a short
        fill = self.cost_model.fill_price(price, closing_direction)
        self.cash += self.position * fill
        commission = self.cost_model.commission(self.position * fill)
        self.cash -= commission

        trade = self._open_trade
        trade.exit_time = when
        trade.exit_price = fill
        trade.commission += commission
        trade.funding = self._funding_accrued
        # Gross PnL on the signed position; net of all costs in ``pnl``.
        trade.gross_pnl = (fill - trade.entry_price) * self.position
        trade.pnl = trade.gross_pnl - trade.commission - trade.funding
        self.trades.append(trade)

        self.position = 0.0
        self._open_trade = None
        self._funding_accrued = 0.0

    def mark(self, price: float, when: datetime) -> None:
        """Append the current equity to the curve."""
        self.equity_curve.append((when, self.equity(price)))
