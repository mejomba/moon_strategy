from django.test import SimpleTestCase

from backtester.engine.indicators import ema, rsi, sma


class IndicatorTests(SimpleTestCase):
    def test_sma_basic(self):
        values = [1, 2, 3, 4, 5]
        result = sma(values, 3)
        self.assertEqual(result[:2], [None, None])
        self.assertAlmostEqual(result[2], 2.0)
        self.assertAlmostEqual(result[3], 3.0)
        self.assertAlmostEqual(result[4], 4.0)

    def test_sma_rejects_bad_period(self):
        with self.assertRaises(ValueError):
            sma([1, 2, 3], 0)

    def test_ema_seeds_with_sma(self):
        values = [float(i) for i in range(1, 11)]
        result = ema(values, 3)
        self.assertIsNone(result[1])
        # First defined EMA equals the SMA of the first `period` values.
        self.assertAlmostEqual(result[2], 2.0)
        self.assertIsNotNone(result[-1])

    def test_rsi_all_gains_is_100(self):
        values = [float(i) for i in range(1, 20)]
        result = rsi(values, 14)
        self.assertAlmostEqual(result[-1], 100.0)

    def test_rsi_bounds(self):
        values = [1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 8, 7, 9, 8, 10]
        result = rsi([float(v) for v in values], 14)
        for v in result:
            if v is not None:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)
