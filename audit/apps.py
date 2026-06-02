from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Activity & Audit Log"

    def ready(self):
        from .signals import register_audit_signals

        register_audit_signals()
