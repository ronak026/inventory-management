from django.contrib import admin

from .models import BOMComponent, WorkOrder, WorkOrderComponent


class BOMComponentInline(admin.TabularInline):
    model = BOMComponent
    fk_name = "product"
    extra = 1
    autocomplete_fields = ("component",)


@admin.register(BOMComponent)
class BOMComponentAdmin(admin.ModelAdmin):
    list_display = ("product", "component", "quantity")
    search_fields = ("product__name", "component__name")
    autocomplete_fields = ("product", "component")


class WorkOrderComponentInline(admin.TabularInline):
    model = WorkOrderComponent
    extra = 0
    readonly_fields = ("component", "required_quantity", "consumed_quantity")
    can_delete = False


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "wo_number", "product", "quantity", "wo_type", "status",
        "assigned_to", "created_at",
    )
    list_filter = ("status", "wo_type", "created_at")
    search_fields = ("wo_number", "product__name")
    inlines = [WorkOrderComponentInline]
    readonly_fields = (
        "reserved", "produced_quantity", "released_at", "started_at",
        "completed_at", "created_at", "updated_at",
    )
    autocomplete_fields = ("product", "assigned_to", "created_by")
