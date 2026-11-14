from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AgentListView, CategoryListView, MetricsSummaryView, TicketViewSet

router = SimpleRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("metrics/summary/", MetricsSummaryView.as_view(), name="metrics-summary"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("agents/", AgentListView.as_view(), name="agent-list"),
    *router.urls,
]
