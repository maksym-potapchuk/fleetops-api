from django.db import models


class NotificationType(models.TextChoices):
    REGULATION_APPROACHING = "regulation_approaching", "Regulation Approaching"
    REGULATION_OVERDUE = "regulation_overdue", "Regulation Overdue"
    REGULATION_PERFORMED = "regulation_performed", "Regulation Performed"
    MILEAGE_SUBMITTED = "mileage_submitted", "Mileage Submitted"
    SERVICE_REPORT = "service_report", "Service Report"
    INSPECTION_EXPIRING = "inspection_expiring", "Technical Inspection Expiring"
    INSPECTION_EXPIRED = "inspection_expired", "Technical Inspection Expired"
    SERVICE_PLAN_DUE = "service_plan_due", "Service Plan Due"
    SERVICE_PLAN_OVERDUE = "service_plan_overdue", "Service Plan Overdue"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    INFO = "info", "Info"
