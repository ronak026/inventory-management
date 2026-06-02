"""Stock movement model.

Every change to ``Product.current_stock`` is recorded here, giving a full,
auditable transaction history. The applied delta is captured in
``quantity_change`` and ``resulting_stock`` so history stays correct even if
the product's reorder level or prices change later.
"""
from django.conf import settings
from django.db import models, transaction
from django.db.models import F


class TransactionType(models.TextChoices):
    STOCK_IN = "in", "Stock In"
    STOCK_OUT = "out", "Stock Out"
    ADJUSTMENT = "adjust", "Stock Adjustment"


class StockTransaction(models.Model):
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=10, choices=TransactionType.choices, db_index=True
    )
    # For IN/OUT this is a positive magnitude. For ADJUSTMENT it is the signed
    # delta the user wants to apply (e.g. -3 to write off, +5 found stock).
    quantity = models.IntegerField()

    # Audit snapshot of the effect actually applied to stock.
    quantity_change = models.IntegerField(default=0, editable=False)
    resulting_stock = models.IntegerField(default=0, editable=False)

    reference_number = models.CharField(max_length=60, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="stock_transactions",
    )
    # Optional link back to a purchase receipt that generated this movement.
    source_purchase = models.ForeignKey(
        "purchases.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["transaction_type", "-created_at"]),
        ]

    # --- Stock effect -----------------------------------------------------
    def signed_delta(self) -> int:
        """The signed change this transaction applies to current_stock."""
        if self.transaction_type == TransactionType.STOCK_IN:
            return abs(self.quantity)
        if self.transaction_type == TransactionType.STOCK_OUT:
            return -abs(self.quantity)
        return self.quantity  # adjustment: use sign as entered

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Apply the stock delta atomically on first creation only."""
        is_new = self._state.adding
        if is_new:
            from products.models import Product

            delta = self.signed_delta()
            # Lock the product row to avoid race conditions on concurrent moves.
            product = Product.objects.select_for_update().get(pk=self.product_id)
            new_stock = product.current_stock + delta
            self.quantity_change = delta
            self.resulting_stock = new_stock
            Product.objects.filter(pk=product.pk).update(
                current_stock=F("current_stock") + delta
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_transaction_type_display()} · {self.product} · {self.quantity}"
