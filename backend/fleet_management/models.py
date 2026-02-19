from django.db import models


# Create your models here.
class FleetService(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RegulationNotificationStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    SENT = "Sent", "Sent"
    FAILED = "Failed", "Failed"

class EventType(models.TextChoices):
    PERFORMED = "performed", "Service Performed"
    KM_UPDATED = "km_updated", "KM Updated"
    NOTIFIED = "notified", "Notification Sent"

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


class FleetVehicleRegulationSchema(models.Model):
    """A named package of regulation. for example (Basic Regulation)"""

    title = models.CharField(max_length=155, unique=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_regulation_schemas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name='unique_default_schema'
            )
        ]

    def save(self, *args, **kwargs):
        if self.is_default:
            FleetVehicleRegulationSchema.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class FleetVehicleRegulationItem(models.Model):
    """A single regulation related to schema"""

    schema = models.ForeignKey(
        FleetVehicleRegulationSchema, 
        on_delete=models.CASCADE, 
        related_name="items"
    )
    title = models.CharField(max_length=155)
    every_km = models.PositiveIntegerField()
    notify_before_km = models.PositiveIntegerField(default=500)

    class Meta:
        unique_together = ("schema", "title")

    def __str__(self):
        return f"{self.title} every {self.every_km}"


class FleetVehicleRegulation(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle", on_delete=models.CASCADE, related_name="regulations"
    )
    schema = models.ForeignKey(
        FleetVehicleRegulationSchema,
        on_delete=models.PROTECT,
        related_name="regulations",
    )

    assigned_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ("schema", "vehicle")

    def __str__(self):
        return f"{self.vehicle} → {self.schema.title}"


class FleetVehicleRegulationEntry(models.Model):
    """Current state - what's due next for this vehicle item."""

    regulation = models.ForeignKey(
        FleetVehicleRegulation, on_delete=models.CASCADE, related_name="entries"
    )
    item = models.ForeignKey(
        FleetVehicleRegulationItem, on_delete=models.PROTECT, related_name="entries"
    )
    last_done_km = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("regulation", "item")]

    @property
    def next_due_km(self):
        return self.last_done_km + self.item.every_km

    def is_due(self, current_km: int) -> bool:
        return current_km >= self.next_due_km

    def km_remaining(self, current_km: int) -> int:
        return self.next_due_km - current_km

    def __str__(self):
        return f"{self.item.title} → next at {self.next_due_km} km"


class FleetVehicleRegulationHistory(models.Model):
    """Immutable log - every time a regulation item was performed or a km update triggered a check."""

    entry = models.ForeignKey(
        FleetVehicleRegulationEntry,
        on_delete=models.CASCADE, 
        related_name="history"
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    km_at_event = models.PositiveIntegerField()
    km_remaining = models.IntegerField()
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="regulation_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.entry.item.title} [{self.event_type}] at {self.km_at_event} km"


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


class ServicePlan(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="service_plans"
    )
    title = models.CharField(max_length=255) 
    description = models.TextField(null=True, blank=True)
    planned_at = models.DateField()
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vehicle", "title")


class EquipmentDefaultItem(models.Model):
    equipment=models.CharField(max_length=55)
    created_at=models.DateTimeField(auto_now_add=True)


class EquipmentList(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="service_plans"
    )
    equipment=models.CharField(max_length=55)
    is_equipped=models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vehicle", "name")

