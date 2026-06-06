"""Routes for the market-data API (mounted under ``/api/marketdata/``)."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from marketdata.api import CandleImportView, DatasetDeleteView, DatasetViewSet

router = DefaultRouter()
router.register("datasets", DatasetViewSet, basename="dataset")

urlpatterns = [
    path("import/", CandleImportView.as_view(), name="marketdata-import"),
    # Datasets are keyed by (symbol, timeframe), so delete uses a two-segment path
    # that doesn't collide with the router's single-pk detail route.
    path(
        "datasets/<str:symbol>/<str:timeframe>/",
        DatasetDeleteView.as_view(),
        name="marketdata-dataset-delete",
    ),
    *router.urls,
]
