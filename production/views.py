from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView

from accounts.permissions import RoleRequiredMixin
from products.models import Product
from .forms import AssignForm, BOMComponentFormSet, WorkOrderForm
from .models import WorkOrder, WorkOrderStatus


# --- Permission gates --------------------------------------------------------
class PlannerRequiredMixin(RoleRequiredMixin):
    allowed_roles = ("admin", "manager", "planner")


def _require(request, predicate):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not predicate:
        raise PermissionDenied


# --- Work order list / detail ------------------------------------------------
class WorkOrderListView(LoginRequiredMixin, ListView):
    model = WorkOrder
    template_name = "production/wo_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        qs = WorkOrder.objects.select_related("product", "assigned_to", "created_by")
        status = self.request.GET.get("status")
        q = self.request.GET.get("q")
        if self.request.GET.get("mine") and self.request.user.is_authenticated:
            qs = qs.filter(assigned_to=self.request.user)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(wo_number__icontains=q) | Q(product__name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = WorkOrderStatus.choices
        ctx["query"] = self.request.GET.dict()
        return ctx


class WorkOrderDetailView(LoginRequiredMixin, DetailView):
    model = WorkOrder
    template_name = "production/wo_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return WorkOrder.objects.select_related(
            "product", "assigned_to", "created_by"
        ).prefetch_related("components__component")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["assign_form"] = AssignForm()
        return ctx


# --- Create / edit (planner) -------------------------------------------------
def workorder_create(request):
    _require(request, request.user.can_plan_production)
    form = WorkOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        wo = form.save(commit=False)
        wo.created_by = request.user
        wo.save()
        wo.build_components_from_bom()
        if wo.wo_type == "assembly" and not wo.components.exists():
            messages.warning(
                request,
                "This product has no Bill of Materials, so no components were "
                "reserved. Add a BOM on the product to auto-fill components.",
            )
        messages.success(request, f"Work order {wo.wo_number} created.")
        return redirect(wo.get_absolute_url())
    return render(request, "production/wo_form.html", {"form": form})


def workorder_edit(request, pk):
    wo = get_object_or_404(WorkOrder, pk=pk)
    _require(request, request.user.can_plan_production)
    if not wo.is_editable:
        messages.warning(request, "Only draft work orders can be edited.")
        return redirect(wo.get_absolute_url())
    form = WorkOrderForm(request.POST or None, instance=wo)
    if request.method == "POST" and form.is_valid():
        wo = form.save()
        wo.build_components_from_bom()
        messages.success(request, "Work order updated.")
        return redirect(wo.get_absolute_url())
    return render(request, "production/wo_form.html", {"form": form, "order": wo})


# --- Lifecycle actions -------------------------------------------------------
def _post_action(request, pk, predicate, fn_name):
    wo = get_object_or_404(WorkOrder, pk=pk)
    _require(request, predicate(request.user))
    if request.method == "POST":
        ok, msg = getattr(wo, fn_name)(user=request.user)
        (messages.success if ok else messages.warning)(request, msg)
    return redirect(wo.get_absolute_url())


def workorder_release(request, pk):
    return _post_action(request, pk, lambda u: u.can_plan_production, "release")


def workorder_start(request, pk):
    return _post_action(request, pk, lambda u: u.can_execute_production, "start")


def workorder_complete(request, pk):
    return _post_action(request, pk, lambda u: u.can_execute_production, "complete")


def workorder_cancel(request, pk):
    return _post_action(request, pk, lambda u: u.can_plan_production, "cancel")


def workorder_assign(request, pk):
    wo = get_object_or_404(WorkOrder, pk=pk)
    _require(request, request.user.can_supervise_production)
    if request.method == "POST":
        form = AssignForm(request.POST)
        if form.is_valid():
            wo.assign(form.cleaned_data["assigned_to"])
            messages.success(request, f"Assigned to {form.cleaned_data['assigned_to']}.")
        else:
            messages.warning(request, "Please choose a valid technician.")
    return redirect(wo.get_absolute_url())


# --- Bill of materials editor (planner) --------------------------------------
def bom_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    _require(request, request.user.can_plan_production)
    formset = BOMComponentFormSet(request.POST or None, instance=product)
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, f"Bill of materials saved for {product.name}.")
        return redirect("products:product_detail", pk=product.pk)
    return render(request, "production/bom_form.html", {"product": product, "formset": formset})


class WorkOrderDeleteView(PlannerRequiredMixin, DeleteView):
    model = WorkOrder
    template_name = "production/wo_confirm_delete.html"
    success_url = reverse_lazy("production:wo_list")

    def form_valid(self, form):
        # Release any reservations before deleting.
        self.get_object().cancel(user=self.request.user)
        messages.success(self.request, "Work order deleted.")
        return super().form_valid(form)
