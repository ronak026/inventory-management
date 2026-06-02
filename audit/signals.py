"""Connect create/update/delete logging to the tracked domain models."""
from django.db.models.signals import post_delete, post_save

from .middleware import get_current_user

# (app_label, model_name) pairs we track.
TRACKED_MODELS = [
    ("products", "Product"),
    ("products", "Category"),
    ("suppliers", "Supplier"),
    ("purchases", "PurchaseOrder"),
    ("inventory", "StockTransaction"),
    ("accounts", "User"),
]


def _log(instance, action):
    from .models import ActivityLog

    user = get_current_user()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=instance._meta.verbose_name.title(),
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
    )


def _on_save(sender, instance, created, **kwargs):
    _log(instance, "created" if created else "updated")


def _on_delete(sender, instance, **kwargs):
    _log(instance, "deleted")


def register_audit_signals():
    from django.apps import apps

    for app_label, model_name in TRACKED_MODELS:
        model = apps.get_model(app_label, model_name)
        post_save.connect(_on_save, sender=model, dispatch_uid=f"audit_save_{model_name}")
        post_delete.connect(_on_delete, sender=model, dispatch_uid=f"audit_delete_{model_name}")
