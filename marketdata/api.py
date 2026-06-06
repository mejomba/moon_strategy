"""API for importing and listing historical market data."""

from __future__ import annotations

import csv
import io

from django.db.models import Count, Max, Min
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, views, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from marketdata.ingest import clean_rows
from marketdata.models import Candle
from marketdata.serializers import (
    CandleImportSerializer,
    DatasetDeleteResultSerializer,
    DatasetSerializer,
    ImportResultSerializer,
)


class DatasetViewSet(viewsets.ViewSet):
    """List the stored (symbol, timeframe) series and their coverage."""

    @extend_schema(responses=DatasetSerializer(many=True))
    def list(self, request):
        rows = (
            Candle.objects.values("symbol", "timeframe")
            .annotate(count=Count("id"), start=Min("timestamp"), end=Max("timestamp"))
            .order_by("symbol", "timeframe")
        )
        return Response(DatasetSerializer(list(rows), many=True).data)


class DatasetDeleteView(views.APIView):
    """Delete all candles for a (symbol, timeframe) dataset."""

    @extend_schema(responses={200: DatasetDeleteResultSerializer})
    def delete(self, request, symbol: str, timeframe: str):
        deleted, _ = Candle.objects.filter(
            symbol=symbol, timeframe=timeframe
        ).delete()
        return Response(
            DatasetDeleteResultSerializer(
                {"symbol": symbol, "timeframe": timeframe, "deleted": deleted}
            ).data
        )


class CandleImportView(views.APIView):
    """Import a CSV of OHLCV candles for a symbol/timeframe (validated on ingest)."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=CandleImportSerializer,
        responses={201: ImportResultSerializer},
    )
    def post(self, request):
        payload = CandleImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        symbol = payload.validated_data["symbol"].strip()
        timeframe = payload.validated_data["timeframe"].strip()
        upload = payload.validated_data["file"]

        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"errors": ["File must be UTF-8 encoded CSV."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = list(csv.DictReader(io.StringIO(text)))
        report = clean_rows(rows)

        # Persist new candles only; existing (symbol, timeframe, timestamp) stay.
        stored = 0
        if report.cleaned:
            aware = [
                (timezone.make_aware(c.timestamp) if timezone.is_naive(c.timestamp) else c.timestamp, c)
                for c in report.cleaned
            ]
            existing = set(
                Candle.objects.filter(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp__in=[ts for ts, _ in aware],
                ).values_list("timestamp", flat=True)
            )
            to_create = [
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                )
                for ts, c in aware
                if ts not in existing
            ]
            Candle.objects.bulk_create(to_create)
            stored = len(to_create)

        result = {
            "symbol": symbol,
            "timeframe": timeframe,
            "imported": report.imported,
            "stored": stored,
            "skipped": report.skipped,
            "duplicates": report.duplicates,
            "errors": report.errors,
            "start": report.start,
            "end": report.end,
        }
        return Response(
            ImportResultSerializer(result).data, status=status.HTTP_201_CREATED
        )
