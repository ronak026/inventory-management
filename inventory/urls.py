from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("search/", views.global_search, name="search"),
    path("transactions/", views.StockTransactionListView.as_view(), name="transaction_list"),
    path("transactions/add/", views.StockTransactionCreateView.as_view(), name="transaction_add"),
]
