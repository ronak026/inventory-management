from django.contrib import admin

from .models import PurchaseItem, PurchaseOrder


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    autocomplete_fields = ("product",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "po_number", "supplier", "order_date", "status",
        "total_amount", "created_by",
    )
    list_filter = ("status", "order_date", "supplier")
    search_fields = ("po_number", "supplier__name")
    inlines = [PurchaseItemInline]
    readonly_fields = ("total_amount", "received_at", "created_at", "updated_at")
    date_hierarchy = "order_date"

    actions = ["receive_selected"]

    @admin.action(description="Receive stock for selected orders")
    def receive_selected(self, request, queryset):
        count = 0
        for order in queryset:
            if order.can_receive and order.receive_stock(user=request.user):
                count += 1
        self.message_user(request, f"{count} order(s) received.")
