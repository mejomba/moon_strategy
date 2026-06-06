"""Unit tests for the pure ingest cleaning logic (no Django needed)."""

import unittest

from marketdata.ingest import clean_rows


def row(ts, o=10, h=12, low=9, c=11, v=100):
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": v}


class CleanRowsTests(unittest.TestCase):
    def test_cleans_and_sorts_valid_rows(self):
        report = clean_rows([row("2023-01-02"), row("2023-01-01")])
        self.assertEqual(report.imported, 2)
        self.assertEqual(report.skipped, 0)
        # sorted ascending
        self.assertLess(report.cleaned[0].timestamp, report.cleaned[1].timestamp)
        self.assertEqual(report.start, report.cleaned[0].timestamp)
        self.assertEqual(report.end, report.cleaned[1].timestamp)

    def test_missing_column_reports_error(self):
        report = clean_rows([{"timestamp": "2023-01-01", "open": 1}])
        self.assertEqual(report.imported, 0)
        self.assertTrue(any("Missing required column" in e for e in report.errors))

    def test_empty_file(self):
        report = clean_rows([])
        self.assertEqual(report.imported, 0)
        self.assertTrue(report.errors)

    def test_unparseable_row_skipped(self):
        report = clean_rows([row("not-a-date"), row("2023-01-01")])
        self.assertEqual(report.imported, 1)
        self.assertEqual(report.skipped, 1)

    def test_inconsistent_ohlc_skipped(self):
        # high below low
        report = clean_rows([row("2023-01-01", o=10, h=8, low=9, c=10)])
        self.assertEqual(report.imported, 0)
        self.assertEqual(report.skipped, 1)

    def test_non_positive_price_skipped(self):
        report = clean_rows([row("2023-01-01", o=0, h=12, low=0, c=11)])
        self.assertEqual(report.imported, 0)
        self.assertEqual(report.skipped, 1)

    def test_duplicate_timestamps_keep_first(self):
        report = clean_rows([row("2023-01-01", v=100), row("2023-01-01", v=200)])
        self.assertEqual(report.imported, 1)
        self.assertEqual(report.duplicates, 1)
        self.assertEqual(report.cleaned[0].volume, 100)  # first kept

    def test_missing_volume_defaults_to_zero(self):
        r = row("2023-01-01")
        del r["volume"]
        report = clean_rows([r])
        self.assertEqual(report.imported, 1)
        self.assertEqual(report.cleaned[0].volume, 0.0)


if __name__ == "__main__":
    unittest.main()
