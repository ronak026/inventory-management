from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView

from accounts.permissions import StockRecorderRequiredMixin
from . import selectors
from .forms import StockTransactionForm
from .models import StockTransaction, TransactionType


@login_required
def global_search(request):
    """Cross-module search over products, suppliers, purchases and transactions."""
    from products.models import Product
    from suppliers.models import Supplier
    from purchases.models import PurchaseOrder

    q = request.GET.get("q", "").strip()
    products = suppliers = purchases = transactions = []
    if q:
        products = Product.objects.select_related("category").filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )[:20]
        suppliers = Supplier.objects.filter(
            Q(name__icontains=q) | Q(contact_person__icontains=q) | Q(email__icontains=q)
        )[:20]
        purchases = PurchaseOrder.objects.select_related("supplier").filter(
            Q(po_number__icontains=q) | Q(supplier__name__icontains=q)
        )[:20]
        transactions = StockTransaction.objects.select_related("product").filter(
            Q(product__name__icontains=q) | Q(reference_number__icontains=q)
        )[:20]
    total = len(products) + len(suppliers) + len(purchases) + len(transactions)
    return render(request, "search.html", {
        "q": q, "products": products, "suppliers": suppliers,
        "purchases": purchases, "transactions": transactions, "total": total,
    })


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(selectors.dashboard_metrics())

        stock_in = selectors.monthly_movement(TransactionType.STOCK_IN)
        stock_out = selectors.monthly_movement(TransactionType.STOCK_OUT)
        value_trend = selectors.inventory_value_trend()
        top_moving = selectors.top_moving_products()

        # Plain dict — the template's {{ charts|json_script }} encodes it once.
        # (Do NOT json.dumps here, or it gets double-encoded into a string.)
        ctx["charts"] = {
            "stock_in": {"labels": [m for m, _ in stock_in],
                         "values": [v for _, v in stock_in]},
            "stock_out": {"labels": [m for m, _ in stock_out],
                          "values": [v for _, v in stock_out]},
            "value_trend": {"labels": [m for m, _ in value_trend],
                            "values": [v for _, v in value_trend]},
            "top_moving": {"labels": [p for p, _ in top_moving],
                           "values": [v for _, v in top_moving]},
        }
        ctx["low_stock_products"] = selectors.low_stock_products()[:10]
        ctx["recent_transactions"] = (
            StockTransaction.objects.select_related("product", "user")[:10]
        )
        return ctx


class StockTransactionListView(LoginRequiredMixin, ListView):
    model = StockTransaction
    template_name = "inventory/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 20

    def get_queryset(self):
        qs = StockTransaction.objects.select_related("product", "user")
        ttype = self.request.GET.get("type")
        q = self.request.GET.get("q")
        if ttype:
            qs = qs.filter(transaction_type=ttype)
        if q:
            qs = qs.filter(
                Q(product__name__icontains=q)
                | Q(product__sku__icontains=q)
                | Q(reference_number__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["transaction_types"] = TransactionType.choices
        ctx["query"] = self.request.GET.dict()
        return ctx


class StockTransactionCreateView(StockRecorderRequiredMixin, CreateView):
    """Staff and above can record stock movements; auditors are blocked."""

    model = StockTransaction
    form_class = StockTransactionForm
    template_name = "inventory/transaction_form.html"
    success_url = reverse_lazy("inventory:transaction_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Stock transaction recorded.")
        return super().form_valid(form)
