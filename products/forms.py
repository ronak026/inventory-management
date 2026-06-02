from django import forms

from accounts.forms import StyledFormMixin
from .models import Category, Product


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name", "sku", "barcode", "category", "description", "unit",
            "purchase_price", "selling_price", "reorder_level", "status", "image",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        purchase = cleaned.get("purchase_price")
        selling = cleaned.get("selling_price")
        if purchase is not None and selling is not None and selling < purchase:
            self.add_error(
                "selling_price",
                "Selling price is lower than purchase price — please confirm.",
            )
        return cleaned
