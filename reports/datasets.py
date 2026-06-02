"""Report datasets: each returns (title, headers, rows) for any exporter.

A dataset is a pure function of request.GET so the same definition powers the
HTML preview and the Excel / CSV / PDF exports.
"""
from datetime import datetime, timedelta

from django.db.models import F
from django.utils import timezone

from inventory.models import StockTransaction
from products.models import Product
from purchases.models import PurchaseOrder

# Quick date presets: querystring value -> number of days back (None = special).
PERIOD_PRESETS = {"7": 7, "15": 15, "30": 30, "90": 90, "month": None}


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def date_bounds(params):
    """Resolve (start, end) from a `period` preset or explicit start/end.

    `period` may be 7/15/30/90 (last N days) or "month" (month-to-date).
    A preset takes precedence over manual start/end.
    """
    period = params.get("period")
    if period in PERIOD_PRESETS:
        today = timezone.localdate()
        if period == "month":
            return today.replace(day=1), today
        return today - timedelta(days=PERIOD_PRESETS[period] - 1), today
    return _parse_date(params.get("start")), _parse_date(params.get("end"))


def inventory_report(params):
    qs = Product.objects.select_related("category").order_by("name")
    category = params.get("category")
    if category:
        qs = qs.filter(category_id=category)
    # Optional date range -> only products with stock activity in that window.
    start, end = date_bounds(params)
    if start:
        qs = qs.filter(transactions__created_at__date__gte=start)
    if end:
        qs = qs.filter(transactions__created_at__date__lte=end)
    if start or end:
        qs = qs.distinct()
    headers = [
        "SKU", "Product", "Category", "Unit", "Stock",
        "Reorder", "Purchase Price", "Selling Price", "Stock Value", "Status",
    ]
    rows = [
        [
            p.sku, p.name, p.category.name, p.get_unit_display(), p.current_stock,
            p.reorder_level, float(p.purchase_price), float(p.selling_price),
            float(p.stock_value), p.get_status_display(),
        ]
        for p in qs
    ]
    return "Inventory Report", headers, rows


def stock_movement_report(params):
    qs = StockTransaction.objects.select_related("product", "user").order_by(
        "-created_at"
    )
    start, end = date_bounds(params)
    ttype = params.get("type")
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)
    if ttype:
        qs = qs.filter(transaction_type=ttype)
    headers = [
        "Date", "Product", "Type", "Quantity", "Change",
        "Resulting Stock", "Reference", "User",
    ]
    rows = [
        [
            timezone.localtime(t.created_at).strftime("%Y-%m-%d %H:%M"),
            t.product.name, t.get_transaction_type_display(), t.quantity,
            t.quantity_change, t.resulting_stock, t.reference_number,
            t.user.username if t.user else "-",
        ]
        for t in qs
    ]
    return "Stock Movement Report", headers, rows


def low_stock_report(params):
    qs = (
        Product.objects.active()
        .filter(current_stock__lte=F("reorder_level") + F("reserved_stock"))
        .select_related("category")
        .order_by("current_stock")
    )
    headers = ["SKU", "Product", "Category", "Current Stock", "Reorder Level", "Shortfall"]
    rows = [
        [
            p.sku, p.name, p.category.name, p.current_stock, p.reorder_level,
            max(p.reorder_level - p.current_stock, 0),
        ]
        for p in qs
    ]
    return "Low Stock Report", headers, rows


def purchase_report(params):
    qs = PurchaseOrder.objects.select_related("supplier").order_by("-order_date")
    start, end = date_bounds(params)
    status = params.get("status")
    if start:
        qs = qs.filter(order_date__gte=start)
    if end:
        qs = qs.filter(order_date__lte=end)
    if status:
        qs = qs.filter(status=status)
    headers = ["PO Number", "Supplier", "Order Date", "Status", "Total Amount"]
    rows = [
        [
            po.po_number, po.supplier.name, po.order_date.strftime("%Y-%m-%d"),
            po.get_status_display(), float(po.total_amount),
        ]
        for po in qs
    ]
    return "Purchase Report", headers, rows


REPORTS = {
    "inventory": inventory_report,
    "stock-movement": stock_movement_report,
    "low-stock": low_stock_report,
    "purchase": purchase_report,
}
