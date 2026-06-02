from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.permissions import ManagerRequiredMixin
from .filters import filter_products
from .forms import CategoryForm, ProductForm
from .models import Category, Product


# --- Categories ------------------------------------------------------------
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "products/category_list.html"
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        qs = Category.objects.annotate(num_products=Count("products")).order_by("name")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class CategoryCreateView(ManagerRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "products/category_form.html"
    success_url = reverse_lazy("products:category_list")

    def form_valid(self, form):
        messages.success(self.request, "Category created.")
        return super().form_valid(form)


class CategoryUpdateView(ManagerRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "products/category_form.html"
    success_url = reverse_lazy("products:category_list")

    def form_valid(self, form):
        messages.success(self.request, "Category updated.")
        return super().form_valid(form)


class CategoryDeleteView(ManagerRequiredMixin, DeleteView):
    model = Category
    template_name = "products/category_confirm_delete.html"
    success_url = reverse_lazy("products:category_list")

    def form_valid(self, form):
        messages.success(self.request, "Category deleted.")
        return super().form_valid(form)


# --- Products --------------------------------------------------------------
class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 15

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        return filter_products(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.all()
        ctx["query"] = self.request.GET.dict()
        return ctx


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["transactions"] = self.object.transactions.select_related(
            "user"
        ).all()[:15]
        return ctx


class ProductCreateView(ManagerRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Product created.")
        return super().form_valid(form)


class ProductUpdateView(ManagerRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Product updated.")
        return super().form_valid(form)


class ProductDeleteView(ManagerRequiredMixin, DeleteView):
    model = Product
    template_name = "products/product_confirm_delete.html"
    success_url = reverse_lazy("products:product_list")

    def form_valid(self, form):
        messages.success(self.request, "Product deleted.")
        return super().form_valid(form)
