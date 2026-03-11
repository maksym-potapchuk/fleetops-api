import uuid

from django.db import models

from .constants import NotificationStatus, NotificationType


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.INFO,
        db_index=True,
    )

    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    payload = models.JSONField(default=dict)

    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_notifications",
    )

    # ── Delivery tracking ────────────────────────────────────────────────────
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_to = models.CharField(
        max_length=50,
        blank=True,
        help_text="Channel where the notification was delivered (e.g. 'web', 'telegram').",
    )
    retry_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When to re-send this notification. Null means no repeat.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.type}] {self.vehicle or '—'} ({self.status})"
