from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView

from accounts.permissions import ManagerRequiredMixin
from .forms import PurchaseItemFormSet, PurchaseOrderForm
from .invoice import build_purchase_pdf
from .models import PurchaseOrder, PurchaseStatus


@login_required
def purchase_invoice(request, pk):
    """Download a printable PDF (purchase order / invoice) for a PO."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "created_by")
        .prefetch_related("items__product"),
        pk=pk,
    )
    pdf = build_purchase_pdf(order)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="PO-{order.po_number}.pdf"'
    )
    return response


class PurchaseListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = "purchases/purchase_list.html"
    context_object_name = "orders"
    paginate_by = 15

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related("supplier")
        status = self.request.GET.get("status")
        q = self.request.GET.get("q")
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(po_number__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = PurchaseStatus.choices
        ctx["query"] = self.request.GET.dict()
        return ctx


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = "purchases/purchase_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return PurchaseOrder.objects.select_related("supplier", "created_by")


def _render_form(request, order, form, formset):
    return render(
        request,
        "purchases/purchase_form.html",
        {"form": form, "formset": formset, "order": order},
    )


class _ManagerMixin(ManagerRequiredMixin):
    """Marker to keep create/edit guarded for managers and admins."""


def purchase_create(request):
    guard = _ManagerMixin()
    guard.request = request
    if not guard.test_func():
        from django.core.exceptions import PermissionDenied

        if not request.user.is_authenticated:
            return redirect("accounts:login")
        raise PermissionDenied

    form = PurchaseOrderForm(request.POST or None)
    formset = PurchaseItemFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            formset.instance = order
            formset.save()
            order.recalculate_total()
        messages.success(request, f"Purchase order {order.po_number} created.")
        return redirect(order.get_absolute_url())
    return _render_form(request, None, form, formset)


def purchase_edit(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    guard = _ManagerMixin()
    guard.request = request
    if not guard.test_func():
        from django.core.exceptions import PermissionDenied

        if not request.user.is_authenticated:
            return redirect("accounts:login")
        raise PermissionDenied

    if not order.is_editable:
        messages.warning(request, "This order can no longer be edited.")
        return redirect(order.get_absolute_url())

    form = PurchaseOrderForm(request.POST or None, instance=order)
    formset = PurchaseItemFormSet(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
            order.recalculate_total()
        messages.success(request, "Purchase order updated.")
        return redirect(order.get_absolute_url())
    return _render_form(request, order, form, formset)


def purchase_receive(request, pk):
    """Receive stock against a PO — supports partial receipts (qty per line)."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier"), pk=pk
    )
    guard = _ManagerMixin()
    guard.request = request
    if not guard.test_func():
        from django.core.exceptions import PermissionDenied

        if not request.user.is_authenticated:
            return redirect("accounts:login")
        raise PermissionDenied

    if not order.can_receive:
        messages.warning(request, "Order cannot be received in its current state.")
        return redirect(order.get_absolute_url())

    items = order.items.select_related("product")

    if request.method == "POST":
        # "receive_all" button -> receive every outstanding unit.
        if request.POST.get("receive_all"):
            quantities = {i.id: i.outstanding for i in items}
        else:
            quantities = {}
            for item in items:
                raw = request.POST.get(f"qty_{item.id}", "0")
                try:
                    quantities[item.id] = max(0, int(raw or 0))
                except (TypeError, ValueError):
                    quantities[item.id] = 0
        received = order.receive_quantities(quantities, user=request.user)
        if received:
            messages.success(
                request, f"Received {received} unit(s); inventory updated."
            )
        else:
            messages.info(request, "Nothing was received (quantities were zero).")
        return redirect(order.get_absolute_url())

    return render(request, "purchases/purchase_receive.html", {"order": order, "items": items})


class PurchaseDeleteView(ManagerRequiredMixin, DeleteView):
    model = PurchaseOrder
    template_name = "purchases/purchase_confirm_delete.html"
    success_url = reverse_lazy("purchases:list")

    def form_valid(self, form):
        messages.success(self.request, "Purchase order deleted.")
        return super().form_valid(form)
