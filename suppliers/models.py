from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

phone_validator = RegexValidator(
    regex=r"^[0-9+\-\s()]{6,20}$",
    message="Enter a valid phone number.",
)


class Supplier(models.Model):
    name = models.CharField("Supplier name", max_length=200, db_index=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    address = models.TextField(blank=True)
    gst_number = models.CharField("GST / VAT number", max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "gst_number"],
                name="unique_supplier_name_gst",
                condition=~models.Q(gst_number=""),
            )
        ]

    def get_absolute_url(self):
        return reverse("suppliers:detail", args=[self.pk])

    @property
    def purchase_count(self) -> int:
        return self.purchase_orders.count()

    def __str__(self) -> str:
        return self.name
