"""Catalog models: Category and Product.

``Product.current_stock`` is the source of truth for on-hand quantity and is
mutated only through ``inventory.StockTransaction`` (and purchase receipts),
never edited directly in normal flows.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"
        indexes = [models.Index(fields=["name"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("products:category_list")

    @property
    def product_count(self) -> int:
        return self.products.count()

    def __str__(self) -> str:
        return self.name


class Unit(models.TextChoices):
    PIECE = "pcs", "Piece"
    BOX = "box", "Box"
    KILOGRAM = "kg", "Kilogram"
    GRAM = "g", "Gram"
    LITRE = "ltr", "Litre"
    METER = "m", "Meter"
    PACK = "pack", "Pack"
    DOZEN = "dozen", "Dozen"


class ProductStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DISCONTINUED = "discontinued", "Discontinued"


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=ProductStatus.ACTIVE)

    def low_stock(self):
        # available (current - reserved) at or below reorder level.
        return self.filter(
            current_stock__lte=models.F("reorder_level") + models.F("reserved_stock")
        )


class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    sku = models.CharField("SKU", max_length=60, unique=True, db_index=True)
    barcode = models.CharField(max_length=60, blank=True, db_index=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)

    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    current_stock = models.IntegerField(default=0)
    # Soft-allocated to released work orders; not yet consumed.
    reserved_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    status = models.CharField(
        max_length=15, choices=ProductStatus.choices, default=ProductStatus.ACTIVE
    )
    image = models.ImageField(upload_to="products/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["status"]),
            models.Index(fields=["category", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purchase_price__gte=0),
                name="product_purchase_price_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="product_selling_price_gte_0",
            ),
        ]

    # --- Derived data -----------------------------------------------------
    @property
    def available_stock(self) -> int:
        """On-hand minus what's reserved for work orders."""
        return self.current_stock - self.reserved_stock

    @property
    def is_low_stock(self) -> bool:
        # Reserved stock isn't really available, so judge against availability.
        return self.available_stock <= self.reorder_level

    @property
    def has_bom(self) -> bool:
        """True if this product has a bill of materials (is manufacturable)."""
        return self.bom_items.exists()

    @property
    def stock_value(self):
        """On-hand value at purchase price."""
        return self.current_stock * self.purchase_price

    @property
    def potential_revenue(self):
        return self.current_stock * self.selling_price

    def get_absolute_url(self):
        return reverse("products:product_detail", args=[self.pk])

    def __str__(self) -> str:
        return f"{self.name} [{self.sku}]"
