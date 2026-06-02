from django.urls import path

from . import views

app_name = "purchases"

urlpatterns = [
    path("", views.PurchaseListView.as_view(), name="list"),
    path("add/", views.purchase_create, name="add"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.purchase_edit, name="edit"),
    path("<int:pk>/receive/", views.purchase_receive, name="receive"),
    path("<int:pk>/invoice/", views.purchase_invoice, name="invoice"),
    path("<int:pk>/delete/", views.PurchaseDeleteView.as_view(), name="delete"),
]
