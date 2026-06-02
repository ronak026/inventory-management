"""Activity / audit log — an append-only record of who changed what."""
from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="activities",
    )
    action = models.CharField(max_length=10, choices=Action.choices, db_index=True)
    model_name = models.CharField(max_length=80, db_index=True)
    object_id = models.CharField(max_length=40, blank=True)
    object_repr = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["model_name", "-timestamp"])]

    def __str__(self) -> str:
        who = self.user.username if self.user else "system"
        return f"{who} {self.action} {self.model_name} {self.object_repr}"
