"""Reusable role-based access control mixins for class-based views.

Roles
-----
- Admin        : full access
- Manager      : manage products / categories / suppliers / stock / purchases
- Staff        : view everything, create stock transactions only

The mixins build on Django's ``UserPassesTestMixin`` so unauthorized users
get a 403 while anonymous users are redirected to login.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to a set of allowed roles.

    Subclasses set ``allowed_roles`` to an iterable of role strings, or
    override ``test_func``. Superusers always pass.
    """

    allowed_roles: tuple[str, ...] = ()
    raise_exception = True  # 403 instead of redirect for logged-in users

    def test_func(self) -> bool:
        user = self.request.user
        if user.is_superuser:
            return True
        return user.role in self.allowed_roles


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("admin",)


class ManagerRequiredMixin(RoleRequiredMixin):
    """Admins and Inventory Managers."""

    allowed_roles = ("admin", "manager")


class StockRecorderRequiredMixin(RoleRequiredMixin):
    """May record stock transactions — everyone except read-only Auditors."""

    allowed_roles = ("admin", "manager", "staff")
