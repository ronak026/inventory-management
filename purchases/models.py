"""Purchase order models.

A ``PurchaseOrder`` groups ``PurchaseItem`` lines. Receiving an order creates
``StockTransaction`` records (type Stock In) which raise on-hand quantities,
keeping inventory and purchase history consistent.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class PurchaseStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ORDERED = "ordered", "Ordered"
    PARTIAL = "partial", "Partially Received"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(models.Model):
    po_number = models.CharField(
        "PO number", max_length=40, unique=True, db_index=True
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    order_date = models.DateField(default=timezone.now)
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=PurchaseStatus.choices,
        default=PurchaseStatus.DRAFT, db_index=True,
    )
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="purchase_orders",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        indexes = [
            models.Index(fields=["status", "-order_date"]),
            models.Index(fields=["po_number"]),
        ]

    def get_absolute_url(self):
        return reverse("purchases:detail", args=[self.pk])

    def recalculate_total(self, save: bool = True):
        total = sum((item.subtotal for item in self.items.all()), start=0)
        self.total_amount = total
        if save:
            super().save(update_fields=["total_amount", "updated_at"])
        return total

    @property
    def is_editable(self) -> bool:
        return self.status in (PurchaseStatus.DRAFT, PurchaseStatus.ORDERED)

    @property
    def can_receive(self) -> bool:
        return self.status in (
            PurchaseStatus.ORDERED, PurchaseStatus.PARTIAL, PurchaseStatus.DRAFT
        )

    @transaction.atomic
    def receive_stock(self, user=None):
        """Receive all outstanding quantities and update inventory.

        Idempotent per line: each item only receives the not-yet-received
        remainder, so receiving twice does not double-count stock.
        """
        from inventory.models import StockTransaction, TransactionType

        if self.status in (PurchaseStatus.RECEIVED, PurchaseStatus.CANCELLED):
            return False

        received_any = False
        for item in self.items.select_related("product"):
            outstanding = item.quantity - item.received_quantity
            if outstanding <= 0:
                continue
            StockTransaction.objects.create(
                product=item.product,
                transaction_type=TransactionType.STOCK_IN,
                quantity=outstanding,
                reference_number=self.po_number,
                notes=f"Received against PO {self.po_number}",
                user=user,
                source_purchase=self,
            )
            item.received_quantity = item.quantity
            item.save(update_fields=["received_quantity"])
            received_any = True

        self.status = PurchaseStatus.RECEIVED
        self.received_at = timezone.now()
        self.save(update_fields=["status", "received_at", "updated_at"])
        return received_any

    @transaction.atomic
    def receive_quantities(self, quantities: dict, user=None) -> int:
        """Receive specific quantities per item (supports partial receipts).

        ``quantities`` maps PurchaseItem id -> quantity to receive now. Each is
        capped at the item's outstanding amount. Status becomes RECEIVED when
        everything is in, otherwise PARTIAL once anything has been received.
        Returns the total units received in this call.
        """
        from inventory.models import StockTransaction, TransactionType

        if self.status in (PurchaseStatus.RECEIVED, PurchaseStatus.CANCELLED):
            return 0

        total_received = 0
        for item in self.items.select_related("product"):
            want = int(quantities.get(item.id, 0) or 0)
            take = max(0, min(want, item.outstanding))
            if take <= 0:
                continue
            StockTransaction.objects.create(
                product=item.product,
                transaction_type=TransactionType.STOCK_IN,
                quantity=take,
                reference_number=self.po_number,
                notes=f"Received against PO {self.po_number}",
                user=user,
                source_purchase=self,
            )
            item.received_quantity += take
            item.save(update_fields=["received_quantity"])
            total_received += take

        fully = all(i.outstanding <= 0 for i in self.items.all())
        any_received = any(i.received_quantity > 0 for i in self.items.all())
        if fully:
            self.status = PurchaseStatus.RECEIVED
            self.received_at = timezone.now()
        elif any_received:
            self.status = PurchaseStatus.PARTIAL
        self.save(update_fields=["status", "received_at", "updated_at"])
        return total_received

    def __str__(self) -> str:
        return f"{self.po_number} · {self.supplier}"


class PurchaseItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="purchase_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    received_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "product"],
                name="unique_product_per_po",
            )
        ]

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def outstanding(self) -> int:
        """Units still to be received for this line."""
        return max(self.quantity - self.received_quantity, 0)

    def __str__(self) -> str:
        return f"{self.product} x{self.quantity}"
