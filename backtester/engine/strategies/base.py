"""Base class and signal conventions for trading strategies.

A strategy maps a sequence of :class:`~backtester.engine.data.Bar` objects to a
sequence of *target positions*, one per bar:

* ``LONG``  (+1) — be fully long at this bar's close
* ``FLAT``  ( 0) — hold no position
* ``SHORT`` (-1) — be fully short at this bar's close

The engine compares consecutive targets and opens/closes trades when the target
changes. Strategies are therefore stateless and easy to test in isolation.
"""

from __future__ import annotations

from backtester.engine.data import Bar

LONG = 1
FLAT = 0
SHORT = -1


class BaseStrategy:
    """Abstract strategy. Subclasses implement :meth:`generate_signals`."""

    #: Human-readable name, overridden by subclasses.
    name = "base"
    #: Default parameter values; merged with user-supplied params.
    defaults: dict = {}

    def __init__(self, **params):
        merged = {**self.defaults, **params}
        self.params = merged
        for key, value in merged.items():
            setattr(self, key, value)

    def generate_signals(self, bars: list[Bar]) -> list[int]:
        """Return a target position (LONG/FLAT/SHORT) for each input bar."""
        raise NotImplementedError

    def __repr__(self):
        return f"{type(self).__name__}({self.params})"
