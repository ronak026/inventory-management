"""Production / Stock Work Order (SWO) models.

A finished product's **Bill of Materials** lists the component products (and
quantity each) needed to build one unit. A **WorkOrder** to build N units
reserves those components, gets assigned to a technician, and on completion
consumes the components (Stock Out) and — for assembly orders — produces the
finished product (Stock In). All stock movements flow through the existing
``inventory.StockTransaction`` so history and the audit log stay consistent.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.urls import reverse
from django.utils import timezone


class BOMComponent(models.Model):
    """One line of a product's bill of materials (a 'recipe' row)."""

    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="bom_items",
        help_text="The finished product being built.",
    )
    component = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="used_in_boms",
        help_text="A raw material / part consumed to build it.",
    )
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text="Units of this component per 1 finished unit.",
    )

    class Meta:
        ordering = ["component__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "component"], name="unique_component_per_bom"
            ),
            models.CheckConstraint(
                condition=~models.Q(product=models.F("component")),
                name="bom_component_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.component} -> {self.product}"


class WorkOrderType(models.TextChoices):
    ASSEMBLY = "assembly", "Assembly (produce finished stock)"
    SERVICE = "service", "Service / Repair (consume only)"


class WorkOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RELEASED = "released", "Released (materials reserved)"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class WorkOrder(models.Model):
    wo_number = models.CharField("SWO number", max_length=40, unique=True, db_index=True)
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="work_orders",
        help_text="Item to build (assembly) or service.",
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    wo_type = models.CharField(
        max_length=10, choices=WorkOrderType.choices, default=WorkOrderType.ASSEMBLY
    )
    status = models.CharField(
        max_length=12, choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.DRAFT, db_index=True,
    )
    reserved = models.BooleanField(default=False)
    produced_quantity = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_work_orders",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_work_orders",
    )
    notes = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def get_absolute_url(self):
        return reverse("production:wo_detail", args=[self.pk])

    # --- State helpers ----------------------------------------------------
    @property
    def is_editable(self) -> bool:
        return self.status == WorkOrderStatus.DRAFT

    @property
    def can_release(self) -> bool:
        return self.status == WorkOrderStatus.DRAFT

    @property
    def can_start(self) -> bool:
        return self.status == WorkOrderStatus.RELEASED

    @property
    def can_complete(self) -> bool:
        return self.status in (WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS)

    @property
    def can_cancel(self) -> bool:
        return self.status in (
            WorkOrderStatus.DRAFT, WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS
        )

    @property
    def shortages(self):
        """Components whose available stock is below what's required."""
        out = []
        for c in self.components.select_related("component"):
            if c.component.available_stock < c.required_quantity:
                out.append(c)
        return out

    # --- Lifecycle --------------------------------------------------------
    def build_components_from_bom(self):
        """Snapshot required components = BOM quantity x order quantity."""
        self.components.all().delete()
        rows = [
            WorkOrderComponent(
                work_order=self, component=bi.component,
                required_quantity=bi.quantity * self.quantity,
            )
            for bi in self.product.bom_items.select_related("component")
        ]
        WorkOrderComponent.objects.bulk_create(rows)

    @transaction.atomic
    def release(self, user=None):
        """Reserve all component stock. Fails (with shortages) if insufficient."""
        if not self.can_release:
            return False, "Only draft orders can be released."
        short = self.shortages
        if short:
            names = ", ".join(c.component.name for c in short)
            return False, f"Insufficient available stock for: {names}."
        from products.models import Product

        for c in self.components.select_related("component"):
            Product.objects.filter(pk=c.component_id).update(
                reserved_stock=F("reserved_stock") + c.required_quantity
            )
        self.status = WorkOrderStatus.RELEASED
        self.reserved = True
        self.released_at = timezone.now()
        self.save(update_fields=["status", "reserved", "released_at", "updated_at"])
        return True, "Materials reserved and order released."

    def assign(self, user_to):
        self.assigned_to = user_to
        self.save(update_fields=["assigned_to", "updated_at"])

    def start(self, user=None):
        if not self.can_start:
            return False, "Order must be released before starting."
        self.status = WorkOrderStatus.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])
        return True, "Work started."

    @transaction.atomic
    def _release_reservations(self):
        from products.models import Product

        if not self.reserved:
            return
        for c in self.components.select_related("component"):
            Product.objects.filter(pk=c.component_id).update(
                reserved_stock=Greatest(F("reserved_stock") - c.required_quantity, 0)
            )
        self.reserved = False

    @transaction.atomic
    def complete(self, user=None):
        """Consume components (Stock Out) and, for assembly, produce the
        finished product (Stock In). Releases reservations."""
        if not self.can_complete:
            return False, "Order cannot be completed in its current state."
        from inventory.models import StockTransaction, TransactionType

        for c in self.components.select_related("component"):
            StockTransaction.objects.create(
                product=c.component,
                transaction_type=TransactionType.STOCK_OUT,
                quantity=c.required_quantity,
                reference_number=self.wo_number,
                notes=f"Consumed by SWO {self.wo_number}",
                user=user,
            )
            c.consumed_quantity = c.required_quantity
            c.save(update_fields=["consumed_quantity"])

        self._release_reservations()

        if self.wo_type == WorkOrderType.ASSEMBLY:
            StockTransaction.objects.create(
                product=self.product,
                transaction_type=TransactionType.STOCK_IN,
                quantity=self.quantity,
                reference_number=self.wo_number,
                notes=f"Produced by SWO {self.wo_number}",
                user=user,
            )
        self.status = WorkOrderStatus.COMPLETED
        self.produced_quantity = self.quantity
        self.completed_at = timezone.now()
        self.save(update_fields=[
            "status", "reserved", "produced_quantity", "completed_at", "updated_at",
        ])
        return True, "Work order completed; inventory updated."

    @transaction.atomic
    def cancel(self, user=None):
        if not self.can_cancel:
            return False, "Order cannot be cancelled now."
        self._release_reservations()
        self.status = WorkOrderStatus.CANCELLED
        self.save(update_fields=["status", "reserved", "updated_at"])
        return True, "Work order cancelled."

    def __str__(self) -> str:
        return f"{self.wo_number} · {self.product} x{self.quantity}"


class WorkOrderComponent(models.Model):
    """Snapshot of a component requirement for a specific work order."""

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="components"
    )
    component = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="work_order_lines"
    )
    required_quantity = models.PositiveIntegerField(default=0)
    consumed_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["component__name"]

    @property
    def available(self) -> int:
        return self.component.available_stock

    @property
    def is_short(self) -> bool:
        return self.component.available_stock < self.required_quantity

    def __str__(self) -> str:
        return f"{self.component} ({self.required_quantity})"
