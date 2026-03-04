from django.db import models


class RegulationNotificationStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    SENT = "Sent", "Sent"
    FAILED = "Failed", "Failed"


class EventType(models.TextChoices):
    PERFORMED = "performed", "Service Performed"
    KM_UPDATED = "km_updated", "KM Updated"
    NOTIFIED = "notified", "Notification Sent"
