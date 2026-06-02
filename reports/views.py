from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from products.models import Category
from purchases.models import PurchaseStatus
from inventory.models import TransactionType
from .datasets import REPORTS, date_bounds
from .exporters import EXPORTERS


@login_required
def report_index(request):
    return render(
        request,
        "reports/index.html",
        {
            "categories": Category.objects.all(),
            "transaction_types": TransactionType.choices,
            "purchase_statuses": PurchaseStatus.choices,
        },
    )


def _add_serial(headers, rows):
    """Prepend a 1-based serial-number ('No.') column to a dataset."""
    headers = ["No.", *headers]
    rows = [[i, *row] for i, row in enumerate(rows, start=1)]
    return headers, rows


@login_required
def report_view(request, slug):
    """HTML preview of a report, with export buttons."""
    builder = REPORTS.get(slug)
    if builder is None:
        raise Http404("Unknown report")
    title, headers, rows = builder(request.GET)
    headers, rows = _add_serial(headers, rows)
    start, end = date_bounds(request.GET)
    return render(
        request,
        "reports/report_detail.html",
        {
            "title": title,
            "headers": headers,
            "rows": rows,
            "slug": slug,
            "query_string": request.GET.urlencode(),
            "row_count": len(rows),
            "range_start": start,
            "range_end": end,
        },
    )


@login_required
def report_export(request, slug, fmt):
    builder = REPORTS.get(slug)
    exporter = EXPORTERS.get(fmt)
    if builder is None or exporter is None:
        raise Http404("Unknown report or format")
    title, headers, rows = builder(request.GET)
    headers, rows = _add_serial(headers, rows)
    return exporter(title, headers, rows)
