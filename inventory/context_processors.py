"""Inject low-stock notifications and pending-approval counts into templates."""
from .selectors import low_stock_products


def notifications(request):
    if not request.user.is_authenticated:
        return {}
    low = low_stock_products()
    ctx = {
        "low_stock_items": low[:8],
        "low_stock_total": low.count(),
    }
    # Pending account approvals — only relevant to admins.
    if getattr(request.user, "is_admin", False):
        from django.contrib.auth import get_user_model

        ctx["pending_user_count"] = (
            get_user_model().objects.filter(is_active=False).count()
        )
    return ctx
