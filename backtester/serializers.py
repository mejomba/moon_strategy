"""DRF serializers — the wire shape of the API.

These define the JSON contract the frontend repo consumes (via the generated
OpenAPI client). Field names and types here are the source of truth; keep the
``parameters`` payload byte-for-byte compatible with the strategy-JSON the
frontend builder produces (CLAUDE.md §4b/§5).
"""

from __future__ import annotations

from rest_framework import serializers

from backtester.models import Backtest, Strategy, Trade


class StrategySerializer(serializers.ModelSerializer):
    """A strategy definition.

    ``parameters`` is a free-form JSON object. It carries the engine-facing
    parameters (e.g. ``fast``/``slow``) at the top level plus a reserved
    ``_meta`` envelope (schema version + logic graph) written by the frontend.
    The backtest engine reads only the keys it knows and ignores the rest.
    """

    class Meta:
        model = Strategy
        fields = [
            "id",
            "name",
            "description",
            "kind",
            "parameters",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TradeSerializer(serializers.ModelSerializer):
    """An individual simulated trade. PnL fields are net of trading costs."""

    class Meta:
        model = Trade
        fields = [
            "id",
            "backtest",
            "side",
            "quantity",
            "entry_time",
            "entry_price",
            "exit_time",
            "exit_price",
            "gross_pnl",
            "commission",
            "funding",
            "pnl",
        ]
        read_only_fields = fields


class BacktestSerializer(serializers.ModelSerializer):
    """Read representation of a backtest run, including aggregate metrics."""

    strategy_name = serializers.CharField(source="strategy.name", read_only=True)

    class Meta:
        model = Backtest
        fields = [
            "id",
            "strategy",
            "strategy_name",
            "symbol",
            "timeframe",
            "start_date",
            "end_date",
            "initial_capital",
            "commission_pct",
            "slippage_bps",
            "spread_bps",
            "funding_rate",
            "funding_interval_hours",
            "status",
            "final_equity",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe_ratio",
            "win_rate_pct",
            "error_message",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


class EquityPointSerializer(serializers.Serializer):
    """One sample of portfolio value on the equity curve."""

    t = serializers.DateTimeField(help_text="Sample timestamp (ISO-8601).")
    equity = serializers.FloatField(help_text="Portfolio value at this time.")


class BacktestDetailSerializer(BacktestSerializer):
    """Backtest read representation including the full equity curve.

    Used for retrieve/create responses; the list endpoint uses the lighter
    :class:`BacktestSerializer` to avoid shipping the curve for every row.
    """

    equity_curve = EquityPointSerializer(many=True, read_only=True)

    class Meta(BacktestSerializer.Meta):
        fields = BacktestSerializer.Meta.fields + ["equity_curve"]
        read_only_fields = fields


class BacktestCreateSerializer(serializers.ModelSerializer):
    """Write payload to queue a backtest run.

    Only the run configuration is accepted; status, metrics and trades are
    produced by the engine. Cost fields are optional and fall back to the
    model's realistic defaults (CLAUDE.md §7) — results are never cost-free.
    """

    class Meta:
        model = Backtest
        fields = [
            "strategy",
            "symbol",
            "timeframe",
            "start_date",
            "end_date",
            "initial_capital",
            "commission_pct",
            "slippage_bps",
            "spread_bps",
            "funding_rate",
            "funding_interval_hours",
        ]

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        return attrs
