"""DRF viewsets exposing strategies, backtests and trades as a JSON API.

Business logic stays out of the views: the backtest engine lives in
``strategy_core`` and is invoked through ``backtester.runner`` (CLAUDE.md §8).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from backtester.models import Backtest, Strategy
from backtester.runner import run_backtest
from backtester.serializers import (
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSerializer,
    StrategySerializer,
    TradeSerializer,
)


class StrategyViewSet(viewsets.ModelViewSet):
    """CRUD for strategy definitions."""

    queryset = Strategy.objects.all()
    serializer_class = StrategySerializer


@extend_schema(tags=["backtests"])
class BacktestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """List/inspect backtests and queue new runs.

    Creating a backtest executes the run synchronously and returns the finished
    record. If the engine fails, the record is returned with ``status=failed``
    and an ``error_message`` rather than surfacing a 500.
    """

    queryset = Backtest.objects.select_related("strategy").all()

    def get_serializer_class(self):
        if self.action == "create":
            return BacktestCreateSerializer
        if self.action == "retrieve":
            return BacktestDetailSerializer
        return BacktestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        strategy_id = self.request.query_params.get("strategy")
        if strategy_id is not None:
            qs = qs.filter(strategy_id=strategy_id)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "strategy",
                int,
                description="Filter runs by strategy id.",
                required=False,
            )
        ],
        responses=BacktestSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=BacktestCreateSerializer,
        responses={201: BacktestDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        write = self.get_serializer(data=request.data)
        write.is_valid(raise_exception=True)
        backtest = write.save()

        # Run synchronously. The runner persists a FAILED status on error, so we
        # swallow the exception here and return the failed record to the client.
        try:
            run_backtest(backtest)
        except Exception:  # noqa: BLE001 - state is recorded on the row
            pass

        backtest.refresh_from_db()
        read = BacktestDetailSerializer(
            backtest, context=self.get_serializer_context()
        )
        return Response(read.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=TradeSerializer(many=True))
    @action(detail=True, methods=["get"])
    def trades(self, request, pk=None):
        """Return the trade log produced by this backtest."""
        backtest = self.get_object()
        queryset = backtest.trades.all()
        page = self.paginate_queryset(queryset)
        serializer = TradeSerializer(page or queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
