"""Read-side query helpers powering the dashboard and notifications.

Kept separate from views so they can be reused by the API and reports.
"""
from datetime import timedelta

from django.db.models import (
    Count, DecimalField, ExpressionWrapper, F, Sum,
)
from django.db.models.functions import TruncMonth
from django.utils import timezone

from inventory.models import StockTransaction, TransactionType
from products.models import Product


def low_stock_products():
    return (
        Product.objects.active()
        .filter(current_stock__lte=F("reorder_level") + F("reserved_stock"))
        .select_related("category")
        .order_by("current_stock")
    )


def total_inventory_value():
    expr = ExpressionWrapper(
        F("current_stock") * F("purchase_price"),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    agg = Product.objects.aggregate(total=Sum(expr))
    return agg["total"] or 0


def monthly_movement(transaction_type: str, months: int = 6):
    """Return [(label, qty), ...] of monthly summed quantities."""
    since = timezone.now() - timedelta(days=months * 31)
    rows = (
        StockTransaction.objects.filter(
            transaction_type=transaction_type, created_at__gte=since
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("quantity"))
        .order_by("month")
    )
    return [(r["month"].strftime("%b %Y"), abs(r["total"] or 0)) for r in rows]


def top_moving_products(limit: int = 5, days: int = 30):
    since = timezone.now() - timedelta(days=days)
    rows = (
        StockTransaction.objects.filter(created_at__gte=since)
        .values("product__name")
        .annotate(moved=Sum("quantity"))
        .order_by("-moved")[:limit]
    )
    return [(r["product__name"], abs(r["moved"] or 0)) for r in rows]


def inventory_value_trend(months: int = 6):
    """Approximate inventory value movement per month from stock-in value."""
    since = timezone.now() - timedelta(days=months * 31)
    value_expr = ExpressionWrapper(
        F("quantity") * F("product__purchase_price"),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    rows = (
        StockTransaction.objects.filter(
            transaction_type=TransactionType.STOCK_IN, created_at__gte=since
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum(value_expr))
        .order_by("month")
    )
    return [(r["month"].strftime("%b %Y"), float(r["total"] or 0)) for r in rows]


def dashboard_metrics():
    from suppliers.models import Supplier
    from products.models import Category

    return {
        "total_products": Product.objects.count(),
        "total_categories": Category.objects.count(),
        "total_suppliers": Supplier.objects.count(),
        "total_inventory_value": total_inventory_value(),
        "active_products": Product.objects.active().count(),
        "low_stock_count": low_stock_products().count(),
    }
