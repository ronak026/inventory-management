from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsManagerOrReadOnly(BasePermission):
    """Read for any authenticated user; write for managers/admins only."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.can_manage_inventory


class IsStaffCanCreate(BasePermission):
    """Read for any authenticated user; create for stock recorders; edit/delete
    for managers only.

    Used for stock transactions: Admin/Manager/Staff record movements, Auditors
    are read-only, and only managers may modify/delete historical records.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return user.is_superuser or user.can_record_transactions
        return user.is_superuser or user.can_manage_inventory
