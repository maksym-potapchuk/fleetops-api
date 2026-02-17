from django.db import models


# Create your models here.
class FleetService(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ServiceHistory(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle", on_delete=models.CASCADE, related_name="service_history"
    )
    service_date = models.DateField()
    service_type = models.CharField(max_length=100)
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_field = models.FileField(upload_to="invoices/")
    invoice_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FleetVehicleRegulation(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle", on_delete=models.CASCADE, related_name="regulations"
    )
    regulation_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vehicle", "regulation_json")


class RegulationNotificationStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    SENT = "Sent", "Sent"
    FAILED = "Failed", "Failed"


class FleetVehicleRegulationNotification(models.Model):
    regulation = models.ForeignKey(
        "fleet_management.FleetVehicleRegulation",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    regulation_name = models.CharField(max_length=100)
    notification_message = models.CharField(max_length=255)
    send_at = models.DateTimeField()
    status = models.CharField(
        choices=RegulationNotificationStatus.choices,
        max_length=20,
        default=RegulationNotificationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# CREATE SPENDING FORM
