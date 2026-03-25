import uuid

from django.db import models

from .constants import NotificationSource, NotificationStatus, NotificationType


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

    source = models.CharField(
        max_length=20,
        choices=NotificationSource.choices,
        default=NotificationSource.SYSTEM,
        db_index=True,
    )

    payload = models.JSONField(default=dict)
    dedup_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique key for deduplication. Format: {type}:{vehicle_id}:{entity_id}",
    )

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


class NotificationPreferences(models.Model):
    """Per-user notification settings — thresholds and toggles."""

    user = models.OneToOneField(
        "account.User",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # ── Enable / disable per category ────────────────────────────────────────
    inspection_enabled = models.BooleanField(default=True)
    regulation_enabled = models.BooleanField(default=True)
    service_plan_enabled = models.BooleanField(default=True)
    mileage_enabled = models.BooleanField(default=True)

    # ── Thresholds ───────────────────────────────────────────────────────────
    inspection_notify_days = models.JSONField(
        default=list,
        help_text="Days before inspection to notify, e.g. [7, 3, 1]",
    )
    service_plan_notify_days = models.JSONField(
        default=list,
        help_text="Days before service plan to notify, e.g. [7, 3, 1]",
    )

    # ── Regulation threshold ─────────────────────────────────────────────────
    regulation_notify_before_km = models.PositiveIntegerField(
        default=500,
        help_text="Global km threshold for regulation approaching notifications. Overrides per-item settings.",
    )

    # ── Overdue reminders ────────────────────────────────────────────────────
    overdue_reminder_interval = models.PositiveIntegerField(
        default=7,
        help_text="Days between overdue reminder notifications.",
    )
    overdue_reminder_max = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of overdue reminders per item.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"NotificationPreferences for {self.user}"

    def save(self, *args, **kwargs):
        if not self.inspection_notify_days:
            self.inspection_notify_days = [7, 3, 1]
        if not self.service_plan_notify_days:
            self.service_plan_notify_days = [3, 1]
        super().save(*args, **kwargs)
