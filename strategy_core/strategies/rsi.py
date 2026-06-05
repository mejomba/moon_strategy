"""RSI mean-reversion strategy."""

from __future__ import annotations

from strategy_core.data import Bar
from strategy_core.indicators import rsi
from strategy_core.strategies.base import FLAT, LONG, BaseStrategy


class RsiStrategy(BaseStrategy):
    """Buy when oversold, exit when overbought (long/flat).

    Enters long when RSI drops below ``oversold`` and holds until RSI rises
    above ``overbought``, at which point the position is closed. The target is
    carried forward between thresholds so the strategy stays in its position.

    Parameters
    ----------
    period: int
        RSI lookback period.
    oversold: float
        Enter long when RSI falls below this level.
    overbought: float
        Exit when RSI rises above this level.
    """

    name = "rsi"
    defaults = {"period": 14, "oversold": 30.0, "overbought": 70.0}

    def generate_signals(self, bars: list[Bar]) -> list[int]:
        closes = [b.close for b in bars]
        values = rsi(closes, self.period)

        signals: list[int] = []
        position = FLAT
        for value in values:
            if value is not None:
                if value < self.oversold:
                    position = LONG
                elif value > self.overbought:
                    position = FLAT
            signals.append(position)
        return signals
