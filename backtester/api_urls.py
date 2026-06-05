"""Router wiring for the JSON API (mounted under ``/api/``)."""

from rest_framework.routers import DefaultRouter

from backtester.api import BacktestViewSet, StrategyViewSet

router = DefaultRouter()
router.register("strategies", StrategyViewSet, basename="strategy")
router.register("backtests", BacktestViewSet, basename="backtest")

urlpatterns = router.urls
