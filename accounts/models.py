"""User & role models.

A single custom ``User`` carries a ``role`` field that drives the
role-based access control used across the project. A one-to-one
``Profile`` stores extended attributes and an avatar.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Inventory Manager"
    STAFF = "staff", "Staff"
    AUDITOR = "auditor", "Auditor"
    # Production / work-order personas
    PLANNER = "planner", "Production Planner"
    SUPERVISOR = "supervisor", "Floor Supervisor"
    TECHNICIAN = "technician", "Technician"


class User(AbstractUser):
    """Project user with a role used for access control."""

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STAFF, db_index=True
    )
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["username"]

    # --- Role helpers -----------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_manager(self) -> bool:
        return self.role == Role.MANAGER

    @property
    def is_staff_member(self) -> bool:
        return self.role == Role.STAFF

    @property
    def is_auditor(self) -> bool:
        """Read-only oversight role — may view everything, change nothing."""
        return self.role == Role.AUDITOR

    @property
    def can_manage_inventory(self) -> bool:
        """Admins and managers can mutate catalog & stock master data."""
        return self.is_admin or self.is_manager

    @property
    def can_record_transactions(self) -> bool:
        """Who may record stock movements: everyone except auditors."""
        return self.is_admin or self.is_manager or self.is_staff_member

    # --- Production / work-order roles -----------------------------------
    @property
    def is_planner(self) -> bool:
        return self.role == Role.PLANNER

    @property
    def is_supervisor(self) -> bool:
        return self.role == Role.SUPERVISOR

    @property
    def is_technician(self) -> bool:
        return self.role == Role.TECHNICIAN

    @property
    def can_plan_production(self) -> bool:
        """Create work orders, manage BOMs, reserve materials."""
        return self.is_admin or self.is_manager or self.is_planner

    @property
    def can_supervise_production(self) -> bool:
        """Assign work orders and track the floor."""
        return self.is_admin or self.is_manager or self.is_supervisor

    @property
    def can_execute_production(self) -> bool:
        """Start and complete assigned work orders."""
        return (
            self.is_admin or self.is_manager
            or self.is_supervisor or self.is_technician
        )

    @property
    def in_production(self) -> bool:
        """Any production persona (for nav visibility)."""
        return (
            self.is_admin or self.is_manager
            or self.is_planner or self.is_supervisor or self.is_technician
        )

    def __str__(self) -> str:
        full = self.get_full_name()
        return f"{full} ({self.get_role_display()})" if full else self.username


class Profile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    job_title = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"
