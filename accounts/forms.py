from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Profile, Role, User


class StyledFormMixin:
    """Apply Tailwind component classes (see partials/tailwind_head.html) to widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            elif isinstance(widget, forms.Textarea):
                css = "form-textarea"
            else:
                css = "form-input"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()


class RegisterForm(StyledFormMixin, UserCreationForm):
    """Public self-registration. New accounts are created as inactive Staff and
    must be approved (activated) by an Admin before they can log in. The role is
    NOT user-selectable — it's forced to Staff."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)  # password already set by UserCreationForm
        user.role = Role.STAFF
        user.is_active = False  # pending admin approval
        if commit:
            user.save()
        return user


class UserCreateForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role")


class UserUpdateForm(StyledFormMixin, UserChangeForm):
    password = None  # hide hashed-password field

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "phone", "role", "is_active",
        )


class SelfProfileForm(StyledFormMixin, forms.ModelForm):
    """Lets a user edit their own basic details (role is read-only)."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("avatar", "job_title", "address")
