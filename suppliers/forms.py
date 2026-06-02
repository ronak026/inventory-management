from django import forms

from accounts.forms import StyledFormMixin
from .models import Supplier


class SupplierForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "name", "contact_person", "email", "phone",
            "address", "gst_number", "is_active",
        )
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
