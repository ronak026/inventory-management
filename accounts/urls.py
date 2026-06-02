from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Auth
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    # Password reset flow
    path("password-reset/", views.AppPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.AppPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", views.AppPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", views.AppPasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # Password change
    path("password-change/", views.password_change, name="password_change"),
    # Profile
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    # User & role management (admin)
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/add/", views.UserCreateView.as_view(), name="user_add"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/approve/", views.user_approve, name="user_approve"),
    path("users/<int:pk>/delete/", views.UserDeleteView.as_view(), name="user_delete"),
]
