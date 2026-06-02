from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("products", views.ProductViewSet, basename="product")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("transactions", views.StockTransactionViewSet, basename="transaction")
router.register("purchases", views.PurchaseOrderViewSet, basename="purchase")
router.register("dashboard", views.DashboardViewSet, basename="dashboard")

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
    path("auth/token/", obtain_auth_token, name="token"),
    path("auth/", include("rest_framework.urls")),  # browsable API login
]
