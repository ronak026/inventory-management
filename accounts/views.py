from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView, PasswordResetConfirmView,
    PasswordResetDoneView, PasswordResetCompleteView,
)
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from .forms import (
    ProfileForm, RegisterForm, SelfProfileForm, StyledFormMixin,
    UserCreateForm, UserUpdateForm,
)
from .models import User
from .permissions import AdminRequiredMixin


# --- Public self-registration (pending admin approval) ---------------------
def _notify_admins_of_registration(new_user):
    """Email active admins so they know to approve a new signup."""
    from django.conf import settings
    from django.core.mail import send_mail
    from django.db.models import Q

    recipients = list(
        User.objects.filter(Q(role="admin") | Q(is_superuser=True), is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return
    send_mail(
        subject="New account pending approval",
        message=(
            f"A new user '{new_user.username}' ({new_user.email}) has registered "
            f"and is awaiting approval.\n\n"
            f"Approve them in Users & Roles."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("inventory:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        _notify_admins_of_registration(user)
        messages.success(
            request,
            "Account created. It's pending administrator approval — you'll be "
            "able to sign in once an admin activates it.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {"form": form})


# --- Authentication --------------------------------------------------------
class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    pass


class AppPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class AppPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    """SetPasswordForm with Tailwind-styled widgets."""


class AppPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class AppPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


# --- Profile ---------------------------------------------------------------
class ProfileView(LoginRequiredMixin, DetailView):
    template_name = "accounts/profile.html"
    context_object_name = "profile_user"

    def get_object(self):
        return self.request.user


def profile_edit(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    user_form = SelfProfileForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(
        request.POST or None, request.FILES or None, instance=request.user.profile
    )
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile_edit.html",
        {"user_form": user_form, "profile_form": profile_form},
    )


def password_change(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    form = PasswordChangeForm(user=request.user, data=request.POST or None)
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-input"
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password changed successfully.")
        return redirect("accounts:profile")
    return render(request, "accounts/password_change.html", {"form": form})


# --- User / role management (Admin only) -----------------------------------
class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.select_related("profile").order_by("username")
        q = self.request.GET.get("q")
        role = self.request.GET.get("role")
        if q:
            from django.db.models import Q

            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        if role:
            qs = qs.filter(role=role)
        return qs


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User created.")
        return super().form_valid(form)


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User updated.")
        return super().form_valid(form)


class UserDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User deleted.")
        return super().form_valid(form)


def user_approve(request, pk):
    """One-click activation of a pending (inactive) account — Admin only."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.user.is_admin:
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST" and not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, f"{user.username} approved and activated.")
    return redirect("accounts:user_list")
