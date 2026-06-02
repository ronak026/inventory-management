from django import forms
from django.forms import inlineformset_factory

from accounts.forms import StyledFormMixin
from accounts.models import Role, User
from products.models import Product, ProductStatus
from .models import BOMComponent, WorkOrder


class WorkOrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ("wo_number", "product", "quantity", "wo_type",
                  "assigned_to", "due_date", "notes")
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.exclude(
            status=ProductStatus.DISCONTINUED
        ).order_by("name")
        # Only technicians (and supervisors) can be assigned work.
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, role__in=[Role.TECHNICIAN, Role.SUPERVISOR]
        ).order_by("username")
        self.fields["assigned_to"].required = False


class AssignForm(StyledFormMixin, forms.Form):
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(
            is_active=True, role__in=[Role.TECHNICIAN, Role.SUPERVISOR]
        ).order_by("username"),
        label="Assign to technician",
    )


class BOMComponentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BOMComponent
        fields = ("component", "quantity")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["component"].queryset = Product.objects.exclude(
            status=ProductStatus.DISCONTINUED
        ).order_by("name")


BOMComponentFormSet = inlineformset_factory(
    Product, BOMComponent, form=BOMComponentForm,
    fk_name="product", extra=3, can_delete=True,
)
