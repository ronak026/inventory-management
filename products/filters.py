"""Lightweight querystring filtering helpers shared by HTML views."""
from django.db.models import F, Q


def filter_products(queryset, params):
    """Apply search & filters from a request.GET-like mapping."""
    q = params.get("q")
    category = params.get("category")
    status = params.get("status")
    stock = params.get("stock")  # "low" | "out" | "in"

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )
    if category:
        queryset = queryset.filter(category_id=category)
    if status:
        queryset = queryset.filter(status=status)
    if stock == "low":
        queryset = queryset.filter(
            current_stock__lte=F("reorder_level") + F("reserved_stock")
        )
    elif stock == "out":
        queryset = queryset.filter(current_stock__lte=F("reserved_stock"))
    elif stock == "in":
        queryset = queryset.filter(current_stock__gt=F("reserved_stock"))

    ordering = params.get("ordering")
    allowed = {"name", "-name", "sku", "-sku", "current_stock", "-current_stock",
               "selling_price", "-selling_price", "created_at", "-created_at"}
    if ordering in allowed:
        queryset = queryset.order_by(ordering)
    return queryset
