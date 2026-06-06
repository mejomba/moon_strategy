"""Routes for the market-data API (mounted under ``/api/marketdata/``)."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from marketdata.api import CandleImportView, DatasetViewSet

router = DefaultRouter()
router.register("datasets", DatasetViewSet, basename="dataset")

urlpatterns = [
    path("import/", CandleImportView.as_view(), name="marketdata-import"),
    *router.urls,
]
