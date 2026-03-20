import uuid

from django.db import models


class Driver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15, unique=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    has_vehicle = models.BooleanField(default=False)
    is_active_driver = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class DriverVehicleDeal(models.Model):
    id = models.UUIDField(primary_key=True)
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="deals",
        db_column="vehicle_id",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.DO_NOTHING,
        related_name="deals",
        db_column="driver_id",
    )
    deal_id = models.UUIDField()

    class Meta:
        managed = False
        db_table = "driver_vehicle_deal"

    def __str__(self) -> str:
        return (
            f"Deal {self.deal_id} — driver={self.driver_id} vehicle={self.vehicle_id}"
        )
