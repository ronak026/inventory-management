"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("products/", include("products.urls")),
    path("suppliers/", include("suppliers.urls")),
    path("purchases/", include("purchases.urls")),
    path("reports/", include("reports.urls")),
    path("production/", include("production.urls")),
    path("activity/", include("audit.urls")),
    path("api/", include("api.urls")),
    # Inventory app owns the dashboard at the site root.
    path("", include("inventory.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

# Branding for the Django admin
admin.site.site_header = "Inventory Management Administration"
admin.site.site_title = "Inventory Admin"
admin.site.index_title = "Operations Console"
