from django import forms
from django.forms import inlineformset_factory

from accounts.forms import StyledFormMixin
from products.models import Product, ProductStatus
from .models import PurchaseItem, PurchaseOrder


class PurchaseOrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = (
            "po_number", "supplier", "order_date",
            "expected_date", "status", "notes",
        )
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class PurchaseItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ("product", "quantity", "unit_price")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.exclude(
            status=ProductStatus.DISCONTINUED
        ).order_by("name")


PurchaseItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseItem,
    form=PurchaseItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
