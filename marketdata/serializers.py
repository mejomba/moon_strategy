from rest_framework import serializers


class CandleImportSerializer(serializers.Serializer):
    """Multipart payload to import a CSV of OHLCV candles."""

    symbol = serializers.CharField(max_length=32)
    timeframe = serializers.CharField(max_length=8)
    file = serializers.FileField(
        help_text="CSV with columns: timestamp, open, high, low, close[, volume]."
    )


class ImportResultSerializer(serializers.Serializer):
    """Summary of an import run."""

    symbol = serializers.CharField()
    timeframe = serializers.CharField()
    imported = serializers.IntegerField()
    stored = serializers.IntegerField(help_text="New candles written (excludes existing).")
    skipped = serializers.IntegerField()
    duplicates = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField())
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)


class DatasetSerializer(serializers.Serializer):
    """A stored (symbol, timeframe) series with its coverage."""

    symbol = serializers.CharField()
    timeframe = serializers.CharField()
    count = serializers.IntegerField()
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)


class DatasetDeleteResultSerializer(serializers.Serializer):
    """Result of deleting a dataset."""

    symbol = serializers.CharField()
    timeframe = serializers.CharField()
    deleted = serializers.IntegerField(help_text="Number of candles removed.")
