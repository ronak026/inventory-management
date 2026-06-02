from django.db.models import Count, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from inventory.models import StockTransaction
from inventory.selectors import dashboard_metrics
from products.models import Category, Product
from purchases.models import PurchaseOrder
from suppliers.models import Supplier
from .permissions import IsManagerOrReadOnly, IsStaffCanCreate
from .serializers import (
    CategorySerializer, ProductSerializer, PurchaseOrderSerializer,
    StockTransactionSerializer, SupplierSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    # Annotate as `num_products` (not `product_count`, which is a read-only
    # model property and would clash when Django assigns the annotation).
    queryset = Category.objects.annotate(num_products=Count("products")).order_by("name")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsManagerOrReadOnly]
    queryset = Product.objects.select_related("category")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "status", "unit"]
    search_fields = ["name", "sku", "barcode"]
    ordering_fields = ["name", "current_stock", "selling_price", "created_at"]

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        qs = self.get_queryset().filter(
            current_stock__lte=F("reorder_level") + F("reserved_stock")
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsManagerOrReadOnly]
    queryset = Supplier.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "contact_person", "email", "phone", "gst_number"]
    ordering_fields = ["name", "created_at"]


class StockTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = StockTransactionSerializer
    permission_classes = [IsStaffCanCreate]
    queryset = StockTransaction.objects.select_related("product", "user")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["transaction_type", "product"]
    search_fields = ["product__name", "product__sku", "reference_number"]
    ordering_fields = ["created_at", "quantity"]


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsManagerOrReadOnly]
    queryset = PurchaseOrder.objects.select_related("supplier").prefetch_related("items")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "supplier"]
    search_fields = ["po_number", "supplier__name"]
    ordering_fields = ["order_date", "total_amount"]

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = self.get_object()
        if not order.can_receive:
            return Response(
                {"detail": "Order cannot be received in its current state."},
                status=400,
            )
        order.receive_stock(user=request.user)
        return Response(self.get_serializer(order).data)


class DashboardViewSet(viewsets.ViewSet):
    """Read-only aggregate metrics for dashboards / integrations."""

    def list(self, request):
        return Response(dashboard_metrics())
