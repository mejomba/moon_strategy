import unittest
from datetime import datetime, timedelta, timezone

from strategy_core.costs import CostModel, ZERO_COST
from strategy_core.data import Bar
from strategy_core.engine import BacktestEngine
from strategy_core.strategies.base import FLAT, LONG, BaseStrategy


def _bars_from_closes(closes, days=1):
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=start + timedelta(days=i * days),
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


class _LongThenFlat(BaseStrategy):
    name = "long_then_flat"

    def generate_signals(self, bars):
        half = len(bars) // 2
        return [LONG] * half + [FLAT] * (len(bars) - half)


class CostModelUnitTests(unittest.TestCase):
    def test_negative_params_rejected(self):
        with self.assertRaises(ValueError):
            CostModel(commission_pct=-0.1)
        with self.assertRaises(ValueError):
            CostModel(funding_interval_hours=0)

    def test_fill_price_direction(self):
        cm = CostModel(slippage_bps=5, spread_bps=5)  # 10 bps total
        # Buy fills above, sell below, by 0.1%.
        self.assertAlmostEqual(cm.fill_price(100.0, 1), 100.1)
        self.assertAlmostEqual(cm.fill_price(100.0, -1), 99.9)

    def test_commission_is_fraction_of_notional(self):
        cm = CostModel(commission_pct=0.001)
        self.assertAlmostEqual(cm.commission(5000.0), 5.0)
        self.assertAlmostEqual(cm.commission(-5000.0), 5.0)

    def test_funding_long_pays_short_receives(self):
        cm = CostModel(funding_rate=0.0001, funding_interval_hours=8)
        # One full interval on 10k notional: 0.0001 * 10000 = 1.0
        self.assertAlmostEqual(cm.funding(10_000, 1, 8), 1.0)
        self.assertAlmostEqual(cm.funding(10_000, -1, 8), -1.0)
        # Half an interval -> half the cost.
        self.assertAlmostEqual(cm.funding(10_000, 1, 4), 0.5)

    def test_zero_cost_is_disabled(self):
        self.assertFalse(ZERO_COST.enabled)
        self.assertTrue(CostModel(commission_pct=0.0001).enabled)


class CostImpactTests(unittest.TestCase):
    def test_zero_cost_matches_raw_price_change(self):
        bars = _bars_from_closes([100, 110, 120, 150, 200])
        result = BacktestEngine(initial_capital=1000, cost_model=ZERO_COST).run(
            bars, _AlwaysLong()
        )
        self.assertAlmostEqual(result.metrics.final_equity, 2000.0, places=4)
        self.assertEqual(result.metrics.total_commission, 0.0)

    def test_commission_reduces_return(self):
        bars = _bars_from_closes([100, 110, 120, 150, 200])
        no_cost = BacktestEngine(initial_capital=1000, cost_model=ZERO_COST).run(
            bars, _AlwaysLong()
        )
        with_cost = BacktestEngine(
            initial_capital=1000, cost_model=CostModel(commission_pct=0.001)
        ).run(bars, _AlwaysLong())
        self.assertLess(
            with_cost.metrics.final_equity, no_cost.metrics.final_equity
        )
        self.assertGreater(with_cost.metrics.total_commission, 0.0)
        # Commission is charged on entry and exit (two fills).
        trade = with_cost.trades[0]
        self.assertGreater(trade.commission, 0.0)
        self.assertAlmostEqual(trade.pnl, trade.gross_pnl - trade.commission - trade.funding)

    def test_spread_makes_round_trip_lossy_on_flat_price(self):
        # Price never moves, but crossing the spread twice costs money.
        bars = _bars_from_closes([100, 100, 100, 100])
        result = BacktestEngine(
            initial_capital=1000, cost_model=CostModel(spread_bps=10)
        ).run(bars, _LongThenFlat())
        self.assertLess(result.metrics.final_equity, 1000.0)

    def test_funding_accrues_while_long(self):
        bars = _bars_from_closes([100, 100, 100, 100, 100])
        cm = CostModel(funding_rate=0.001, funding_interval_hours=24)
        result = BacktestEngine(
            initial_capital=1000, timeframe="1d", cost_model=cm
        ).run(bars, _AlwaysLong())
        # A long paying positive funding loses money even on a flat price.
        self.assertGreater(result.metrics.total_funding, 0.0)
        self.assertLess(result.metrics.final_equity, 1000.0)


if __name__ == "__main__":
    unittest.main()
