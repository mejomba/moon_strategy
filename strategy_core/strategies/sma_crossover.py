"""Moving-average crossover strategy."""

from __future__ import annotations

from strategy_core.data import Bar
from strategy_core.indicators import sma
from strategy_core.strategies.base import FLAT, LONG, SHORT, BaseStrategy


class SmaCrossoverStrategy(BaseStrategy):
    """Go long when the fast SMA is above the slow SMA.

    Parameters
    ----------
    fast: int
        Period of the fast moving average.
    slow: int
        Period of the slow moving average.
    allow_short: bool
        If true, go short when the fast SMA is below the slow SMA; otherwise
        move to flat.
    """

    name = "sma_crossover"
    defaults = {"fast": 10, "slow": 30, "allow_short": False}

    def generate_signals(self, bars: list[Bar]) -> list[int]:
        if self.fast >= self.slow:
            raise ValueError("fast period must be smaller than slow period")

        closes = [b.close for b in bars]
        fast_ma = sma(closes, self.fast)
        slow_ma = sma(closes, self.slow)

        bearish = SHORT if self.allow_short else FLAT
        signals: list[int] = []
        for f, s in zip(fast_ma, slow_ma):
            if f is None or s is None:
                signals.append(FLAT)
            elif f > s:
                signals.append(LONG)
            else:
                signals.append(bearish)
        return signals
