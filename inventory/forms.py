from django import forms

from accounts.forms import StyledFormMixin
from products.models import Product, ProductStatus
from .models import StockTransaction, TransactionType


class StockTransactionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockTransaction
        fields = (
            "product", "transaction_type", "quantity",
            "reference_number", "notes",
        )
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.exclude(
            status=ProductStatus.DISCONTINUED
        ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        ttype = cleaned.get("transaction_type")
        qty = cleaned.get("quantity")
        product = cleaned.get("product")
        if qty is None or product is None:
            return cleaned

        if ttype in (TransactionType.STOCK_IN, TransactionType.STOCK_OUT) and qty <= 0:
            self.add_error("quantity", "Quantity must be a positive number.")
        if ttype == TransactionType.ADJUSTMENT and qty == 0:
            self.add_error("quantity", "Adjustment cannot be zero.")

        # Prevent stock going negative.
        if ttype == TransactionType.STOCK_OUT and qty and qty > product.current_stock:
            self.add_error(
                "quantity",
                f"Only {product.current_stock} in stock; cannot remove {qty}.",
            )
        if ttype == TransactionType.ADJUSTMENT and qty and product.current_stock + qty < 0:
            self.add_error(
                "quantity",
                f"Adjustment would make stock negative "
                f"(current {product.current_stock}).",
            )
        return cleaned
