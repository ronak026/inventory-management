from django.urls import path

from . import views

app_name = "suppliers"

urlpatterns = [
    path("", views.SupplierListView.as_view(), name="list"),
    path("add/", views.SupplierCreateView.as_view(), name="add"),
    path("<int:pk>/", views.SupplierDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.SupplierUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.SupplierDeleteView.as_view(), name="delete"),
]
