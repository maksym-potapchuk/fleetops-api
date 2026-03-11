from django.db import models


class NotificationType(models.TextChoices):
    REGULATION_APPROACHING = "regulation_approaching", "Regulation Approaching"
    REGULATION_OVERDUE = "regulation_overdue", "Regulation Overdue"
    MILEAGE_SUBMITTED = "mileage_submitted", "Mileage Submitted"
    SERVICE_REPORT = "service_report", "Service Report"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    INFO = "info", "Info"
