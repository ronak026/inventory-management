from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.permissions import ManagerRequiredMixin
from .forms import SupplierForm
from .models import Supplier


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = "suppliers/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 15

    def get_queryset(self):
        qs = Supplier.objects.all()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(contact_person__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            )
        return qs


class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = "suppliers/supplier_detail.html"
    context_object_name = "supplier"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["purchase_orders"] = self.object.purchase_orders.all()[:15]
        return ctx


class SupplierCreateView(ManagerRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    success_url = reverse_lazy("suppliers:list")

    def form_valid(self, form):
        messages.success(self.request, "Supplier created.")
        return super().form_valid(form)


class SupplierUpdateView(ManagerRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    success_url = reverse_lazy("suppliers:list")

    def form_valid(self, form):
        messages.success(self.request, "Supplier updated.")
        return super().form_valid(form)


class SupplierDeleteView(ManagerRequiredMixin, DeleteView):
    model = Supplier
    template_name = "suppliers/supplier_confirm_delete.html"
    success_url = reverse_lazy("suppliers:list")

    def form_valid(self, form):
        messages.success(self.request, "Supplier deleted.")
        return super().form_valid(form)
