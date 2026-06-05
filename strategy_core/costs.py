"""Trading-cost model: commission, slippage, spread, and funding/swap.

These costs are mandatory for realistic backtests (see CLAUDE.md §7): results
that silently ignore trading costs are misleading. The model is plain data plus
arithmetic so it can be unit-tested in isolation and reused outside the engine.

Conventions
-----------
* ``direction``/``side``: ``+1`` for buy/long, ``-1`` for sell/short.
* ``*_bps`` values are basis points (1 bps = 0.01% = 0.0001).
* ``commission_pct`` / ``funding_rate`` are plain fractions (0.0004 = 0.04%).
* Funding is a periodic cash-flow: longs *pay* when ``funding_rate`` is positive
  and shorts *receive* it (this mirrors crypto perpetual funding).
"""

from __future__ import annotations

from dataclasses import dataclass

_BPS = 10_000.0


@dataclass(frozen=True)
class CostModel:
    """Per-fill and per-holding-period trading costs."""

    commission_pct: float = 0.0  # taker fee per side, fraction of notional
    slippage_bps: float = 0.0  # adverse fill, basis points per side
    spread_bps: float = 0.0  # half-spread crossed per side, basis points
    funding_rate: float = 0.0  # funding per interval, fraction of notional
    funding_interval_hours: float = 8.0

    def __post_init__(self):
        for name in (
            "commission_pct",
            "slippage_bps",
            "spread_bps",
            "funding_interval_hours",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.funding_interval_hours <= 0:
            raise ValueError("funding_interval_hours must be positive")

    @property
    def enabled(self) -> bool:
        """True if any cost component is active."""
        return any(
            (
                self.commission_pct,
                self.slippage_bps,
                self.spread_bps,
                self.funding_rate,
            )
        )

    def fill_price(self, price: float, direction: int) -> float:
        """Execution price for a fill, worse than ``price`` by spread+slippage.

        Buys (direction +1) cross the spread and slip *up*; sells (-1) *down*.
        """
        adjustment = direction * (self.slippage_bps + self.spread_bps) / _BPS
        return price * (1.0 + adjustment)

    def commission(self, notional: float) -> float:
        """Commission charged on a fill of the given notional value."""
        return abs(notional) * self.commission_pct

    def funding(self, notional: float, side: int, hours: float) -> float:
        """Funding cash-flow for holding ``notional`` for ``hours``.

        Returns a positive number for a cost (cash out) and a negative number
        for a credit (cash in). ``side`` is +1 for long, -1 for short.
        """
        if self.funding_rate == 0.0 or hours <= 0:
            return 0.0
        periods = hours / self.funding_interval_hours
        return side * abs(notional) * self.funding_rate * periods


#: A model with all costs disabled (frictionless markets).
ZERO_COST = CostModel()

#: Sensible defaults for a liquid crypto spot/perp pair (taker fees).
DEFAULT_CRYPTO_COST = CostModel(
    commission_pct=0.0004,  # 0.04% taker
    slippage_bps=1.0,
    spread_bps=1.0,
    funding_rate=0.0,
    funding_interval_hours=8.0,
)
