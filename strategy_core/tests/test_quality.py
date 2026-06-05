"""Unit tests for the heuristic quality warnings (no Django)."""

import unittest

from strategy_core.metrics import PerformanceMetrics
from strategy_core.quality import (
    COST_DRAG_RATIO,
    assess_quality,
)


def make_metrics(**overrides) -> PerformanceMetrics:
    defaults = dict(
        final_equity=12000.0,
        total_return_pct=20.0,
        max_drawdown_pct=5.0,
        sharpe_ratio=1.2,
        win_rate_pct=55.0,
        num_trades=100,
        total_commission=0.0,
        total_funding=0.0,
    )
    defaults.update(overrides)
    return PerformanceMetrics(**defaults)


def codes(warnings):
    return {w.code for w in warnings}


class AssessQualityTests(unittest.TestCase):
    def test_in_sample_warning_is_always_present(self):
        warnings = assess_quality(make_metrics(), initial_capital=10000.0)
        self.assertIn("in_sample_only", codes(warnings))

    def test_clean_run_has_only_the_in_sample_warning(self):
        warnings = assess_quality(make_metrics(), initial_capital=10000.0)
        self.assertEqual(codes(warnings), {"in_sample_only"})

    def test_few_trades_warns(self):
        warnings = assess_quality(make_metrics(num_trades=5), initial_capital=10000.0)
        self.assertIn("few_trades", codes(warnings))

    def test_high_sharpe_with_few_trades_flags_overfitting(self):
        warnings = assess_quality(
            make_metrics(sharpe_ratio=4.5, num_trades=20), initial_capital=10000.0
        )
        self.assertIn("overfit_high_sharpe", codes(warnings))

    def test_high_sharpe_with_many_trades_does_not_flag_overfitting(self):
        warnings = assess_quality(
            make_metrics(sharpe_ratio=4.5, num_trades=500), initial_capital=10000.0
        )
        self.assertNotIn("overfit_high_sharpe", codes(warnings))

    def test_cost_drag_warns_when_costs_dominate_gross_profit(self):
        # Net gain 1000 with 2000 of costs → gross 3000, ratio 0.66 > threshold.
        metrics = make_metrics(
            final_equity=11000.0, total_commission=1500.0, total_funding=500.0
        )
        warnings = assess_quality(metrics, initial_capital=10000.0)
        self.assertIn("cost_drag", codes(warnings))

    def test_no_cost_drag_when_costs_are_small(self):
        metrics = make_metrics(
            final_equity=12000.0, total_commission=10.0, total_funding=0.0
        )
        warnings = assess_quality(metrics, initial_capital=10000.0)
        self.assertNotIn("cost_drag", codes(warnings))

    def test_no_cost_drag_on_a_losing_run(self):
        metrics = make_metrics(
            final_equity=9000.0, total_commission=100.0, total_funding=0.0
        )
        warnings = assess_quality(metrics, initial_capital=10000.0)
        self.assertNotIn("cost_drag", codes(warnings))

    def test_threshold_constant_is_a_fraction(self):
        self.assertTrue(0 < COST_DRAG_RATIO < 1)


if __name__ == "__main__":
    unittest.main()
