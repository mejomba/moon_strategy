from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from backtester.engine.data import Bar, generate_synthetic
from backtester.engine.engine import BacktestEngine
from backtester.engine.strategies import SmaCrossoverStrategy, get_strategy
from backtester.engine.strategies.base import FLAT, LONG, BaseStrategy


def _bars_from_closes(closes):
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1.0,
        )
        for i, c in enumerate(closes)
    ]


class _AlwaysLong(BaseStrategy):
    name = "always_long"

    def generate_signals(self, bars):
        return [LONG] * len(bars)


class _BuyAndHoldThenFlat(BaseStrategy):
    """Long for the first half, flat for the second."""

    name = "half"

    def generate_signals(self, bars):
        half = len(bars) // 2
        return [LONG] * half + [FLAT] * (len(bars) - half)


class EngineTests(SimpleTestCase):
    def test_buy_and_hold_return_matches_price_change(self):
        # Price doubles: a fully-invested long should roughly double equity.
        closes = [100, 110, 120, 150, 200]
        bars = _bars_from_closes(closes)
        result = BacktestEngine(initial_capital=1000, timeframe="1d").run(
            bars, _AlwaysLong()
        )
        self.assertAlmostEqual(result.metrics.final_equity, 2000.0, places=4)
        self.assertAlmostEqual(result.metrics.total_return_pct, 100.0, places=4)
        self.assertEqual(result.metrics.num_trades, 1)

    def test_position_closed_at_end(self):
        bars = _bars_from_closes([100, 105, 110])
        result = BacktestEngine(initial_capital=1000).run(bars, _AlwaysLong())
        self.assertEqual(len(result.trades), 1)
        self.assertIsNotNone(result.trades[0].exit_price)
        self.assertFalse(result.trades[0].is_open)

    def test_flat_after_exit_preserves_cash(self):
        # Long while price rises to 200, then flat while it falls to 50.
        closes = [100, 200, 200, 100, 50]
        bars = _bars_from_closes(closes)
        result = BacktestEngine(initial_capital=1000).run(
            bars, _BuyAndHoldThenFlat()
        )
        # Entry at 100, exit at 200 -> equity locked near 2000 once flat.
        self.assertGreater(result.metrics.final_equity, 1900.0)

    def test_winning_trade_counts_in_win_rate(self):
        bars = _bars_from_closes([100, 100, 200, 200])
        result = BacktestEngine(initial_capital=1000).run(
            bars, _BuyAndHoldThenFlat()
        )
        self.assertEqual(result.metrics.win_rate_pct, 100.0)

    def test_empty_bars_raises(self):
        with self.assertRaises(ValueError):
            BacktestEngine().run([], _AlwaysLong())

    def test_signal_length_mismatch_raises(self):
        class _Bad(BaseStrategy):
            def generate_signals(self, bars):
                return [LONG]

        with self.assertRaises(ValueError):
            BacktestEngine().run(_bars_from_closes([1, 2, 3]), _Bad())

    def test_sma_crossover_runs_on_synthetic_data(self):
        bars = generate_synthetic(
            start=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end=datetime(2022, 6, 1, tzinfo=timezone.utc),
            timeframe="1d",
            seed=42,
        )
        strategy = SmaCrossoverStrategy(fast=5, slow=20)
        result = BacktestEngine(initial_capital=10_000).run(bars, strategy)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(len(result.equity_curve), len(bars))

    def test_synthetic_data_is_reproducible(self):
        kwargs = dict(
            start=datetime(2022, 1, 1, tzinfo=timezone.utc),
            end=datetime(2022, 3, 1, tzinfo=timezone.utc),
            timeframe="1d",
            seed=7,
        )
        a = generate_synthetic(**kwargs)
        b = generate_synthetic(**kwargs)
        self.assertEqual([bar.close for bar in a], [bar.close for bar in b])

    def test_registry_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            get_strategy("does_not_exist")

    def test_sma_requires_fast_below_slow(self):
        bars = _bars_from_closes([float(i) for i in range(40)])
        with self.assertRaises(ValueError):
            BacktestEngine().run(bars, SmaCrossoverStrategy(fast=30, slow=10))
