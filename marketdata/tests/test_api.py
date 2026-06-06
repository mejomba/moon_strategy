"""API tests for market-data import and dataset listing."""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from marketdata.models import Candle

CSV = b"""timestamp,open,high,low,close,volume
2023-01-01,100,110,95,105,1000
2023-01-02,105,115,100,112,1200
2023-01-02,105,115,100,112,1200
bad,1,2,3,4,5
"""


def upload(content=CSV, name="data.csv"):
    return SimpleUploadedFile(name, content, content_type="text/csv")


class ImportApiTests(APITestCase):
    def test_import_stores_clean_candles_and_reports_summary(self):
        resp = self.client.post(
            "/api/marketdata/import/",
            {"symbol": "BTCUSDT", "timeframe": "1d", "file": upload()},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["imported"], 2)  # two unique valid rows
        self.assertEqual(resp.data["stored"], 2)
        self.assertEqual(resp.data["duplicates"], 1)
        self.assertEqual(resp.data["skipped"], 1)  # the "bad" row
        self.assertEqual(Candle.objects.filter(symbol="BTCUSDT").count(), 2)

    def test_reimport_does_not_duplicate(self):
        for _ in range(2):
            resp = self.client.post(
                "/api/marketdata/import/",
                {"symbol": "BTCUSDT", "timeframe": "1d", "file": upload()},
                format="multipart",
            )
        self.assertEqual(resp.data["stored"], 0)  # all already present
        self.assertEqual(Candle.objects.filter(symbol="BTCUSDT").count(), 2)

    def test_delete_dataset_removes_candles(self):
        self.client.post(
            "/api/marketdata/import/",
            {"symbol": "BTCUSDT", "timeframe": "1d", "file": upload()},
            format="multipart",
        )
        self.assertEqual(Candle.objects.filter(symbol="BTCUSDT").count(), 2)

        resp = self.client.delete("/api/marketdata/datasets/BTCUSDT/1d/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["deleted"], 2)
        self.assertEqual(Candle.objects.filter(symbol="BTCUSDT").count(), 0)

    def test_delete_missing_dataset_reports_zero(self):
        resp = self.client.delete("/api/marketdata/datasets/NOPE/1d/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["deleted"], 0)

    def test_datasets_lists_coverage(self):
        self.client.post(
            "/api/marketdata/import/",
            {"symbol": "ETHUSDT", "timeframe": "1h", "file": upload()},
            format="multipart",
        )
        resp = self.client.get("/api/marketdata/datasets/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["symbol"], "ETHUSDT")
        self.assertEqual(resp.data[0]["count"], 2)
        self.assertIsNotNone(resp.data[0]["start"])
