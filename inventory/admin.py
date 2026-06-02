from django.contrib import admin

from .models import StockTransaction


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "product", "transaction_type", "quantity",
        "quantity_change", "resulting_stock", "reference_number", "user",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = ("product__name", "product__sku", "reference_number")
    list_select_related = ("product", "user")
    readonly_fields = ("quantity_change", "resulting_stock", "created_at")
    autocomplete_fields = ("product",)
    date_hierarchy = "created_at"
