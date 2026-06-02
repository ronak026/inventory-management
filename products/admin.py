from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "product_count", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "category", "current_stock", "reorder_level",
        "selling_price", "status", "is_low_stock",
    )
    list_filter = ("status", "category", "unit")
    search_fields = ("name", "sku", "barcode")
    list_select_related = ("category",)
    readonly_fields = ("current_stock", "created_at", "updated_at")
    autocomplete_fields = ("category",)
    list_per_page = 25

    @admin.display(boolean=True, description="Low stock")
    def is_low_stock(self, obj):
        return obj.is_low_stock
