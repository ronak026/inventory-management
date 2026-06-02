from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_repr")
    list_filter = ("action", "model_name", "timestamp")
    search_fields = ("object_repr", "model_name", "user__username")
    readonly_fields = ("user", "action", "model_name", "object_id", "object_repr", "timestamp")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False
