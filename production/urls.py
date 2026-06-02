from django.urls import path

from . import views

app_name = "production"

urlpatterns = [
    path("", views.WorkOrderListView.as_view(), name="wo_list"),
    path("add/", views.workorder_create, name="wo_add"),
    path("<int:pk>/", views.WorkOrderDetailView.as_view(), name="wo_detail"),
    path("<int:pk>/edit/", views.workorder_edit, name="wo_edit"),
    path("<int:pk>/release/", views.workorder_release, name="wo_release"),
    path("<int:pk>/assign/", views.workorder_assign, name="wo_assign"),
    path("<int:pk>/start/", views.workorder_start, name="wo_start"),
    path("<int:pk>/complete/", views.workorder_complete, name="wo_complete"),
    path("<int:pk>/cancel/", views.workorder_cancel, name="wo_cancel"),
    path("<int:pk>/delete/", views.WorkOrderDeleteView.as_view(), name="wo_delete"),
    # Bill of materials editor lives under a product.
    path("bom/<int:pk>/", views.bom_edit, name="bom_edit"),
]
