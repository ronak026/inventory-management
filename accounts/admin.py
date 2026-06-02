from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Role & Contact", {"fields": ("role", "phone")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Role & Contact", {"fields": ("role", "phone", "email")}),
    )
