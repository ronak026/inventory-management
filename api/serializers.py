from django.db import transaction
from rest_framework import serializers

from inventory.models import StockTransaction, TransactionType
from products.models import Category, Product
from purchases.models import PurchaseItem, PurchaseOrder
from suppliers.models import Supplier


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    def get_product_count(self, obj):
        # Use the list annotation when present; fall back to the model property
        # (e.g. on the create/update response, which has no annotation).
        annotated = getattr(obj, "num_products", None)
        return annotated if annotated is not None else obj.product_count

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "product_count",
                  "created_at", "updated_at"]
        read_only_fields = ["slug", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "sku", "barcode", "category", "category_name",
            "description", "unit", "purchase_price", "selling_price",
            "current_stock", "reorder_level", "status", "is_low_stock",
            "stock_value", "created_at", "updated_at",
        ]
        # Stock is mutated only via transactions / purchase receipts.
        read_only_fields = ["current_stock", "created_at", "updated_at"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id", "name", "contact_person", "email", "phone",
            "address", "gst_number", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class StockTransactionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )

    class Meta:
        model = StockTransaction
        fields = [
            "id", "product", "product_name", "transaction_type",
            "transaction_type_display", "quantity", "quantity_change",
            "resulting_stock", "reference_number", "notes", "user", "created_at",
        ]
        read_only_fields = ["quantity_change", "resulting_stock", "user", "created_at"]

    def validate(self, attrs):
        ttype = attrs.get("transaction_type")
        qty = attrs.get("quantity")
        product = attrs.get("product")
        if ttype in (TransactionType.STOCK_IN, TransactionType.STOCK_OUT) and qty <= 0:
            raise serializers.ValidationError("Quantity must be positive.")
        if ttype == TransactionType.STOCK_OUT and qty > product.current_stock:
            raise serializers.ValidationError(
                f"Insufficient stock: only {product.current_stock} available."
            )
        if ttype == TransactionType.ADJUSTMENT and product.current_stock + qty < 0:
            raise serializers.ValidationError("Adjustment would make stock negative.")
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = PurchaseItem
        fields = ["id", "product", "product_name", "quantity",
                  "received_quantity", "unit_price", "subtotal"]
        read_only_fields = ["received_quantity"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "supplier", "supplier_name", "order_date",
            "expected_date", "status", "total_amount", "notes", "items",
            "created_at", "updated_at",
        ]
        read_only_fields = ["total_amount", "created_at", "updated_at"]

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        validated_data["created_by"] = self.context["request"].user
        order = PurchaseOrder.objects.create(**validated_data)
        for item in items:
            PurchaseItem.objects.create(purchase_order=order, **item)
        order.recalculate_total()
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for item in items:
                PurchaseItem.objects.create(purchase_order=instance, **item)
            instance.recalculate_total()
        return instance
