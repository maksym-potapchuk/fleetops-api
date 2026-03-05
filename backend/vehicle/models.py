import uuid

from django.db import models

from .constants import FuelType, ManufacturerChoices, VehicleStatus


class Vehicle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.CharField(max_length=50)
    manufacturer = models.CharField(max_length=50, choices=ManufacturerChoices.choices)
    year = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    vin_number = models.CharField(max_length=17, unique=True)
    car_number = models.CharField(max_length=10, unique=True)
    color = models.CharField(max_length=30)
    fuel_type = models.CharField(
        max_length=20,
        choices=FuelType.choices,
        null=True,
        blank=True,
    )
    initial_km = models.PositiveIntegerField(default=0)
    is_selected = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=VehicleStatus.choices,
        default=VehicleStatus.AUCTION,
    )
    status_position = models.PositiveIntegerField(default=0, db_index=True)

    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_vehicles",
    )

    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.car_number} ({self.manufacturer} {self.model})"

    def has_related_data(self) -> bool:
        has_owner = VehicleOwner.objects.filter(vehicle=self).exists()
        return (
            has_owner
            or self.ownership_history.exists()
            or self.photos.exists()
            or self.inspections.exists()
            or self.service_history.exists()
            or self.regulations.exists()
            or self.service_plans.exists()
            or self.equipment_list.exists()
            or self.mileage_logs.exists()
            or self.expenses.exists()
        )


class VehicleOwner(models.Model):
    vehicle = models.OneToOneField(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="current_owner",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.PROTECT,
        related_name="active_vehicles",
    )
    agreement_number = models.CharField(max_length=100, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_vehicle_owners",
    )

    def __str__(self) -> str:
        return f"{self.vehicle} \u2190 {self.driver}"


class OwnerHistory(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="ownership_history",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.PROTECT,
        related_name="past_vehicles",
    )
    agreement_number = models.CharField(max_length=100, blank=True)
    assigned_at = models.DateTimeField()
    unassigned_at = models.DateTimeField()
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_ownership_histories",
    )

    class Meta:
        ordering = ["-unassigned_at"]

    def __str__(self) -> str:
        return f"{self.vehicle} \u2190 {self.driver} ({self.assigned_at} - {self.unassigned_at})"


def vehicle_photo_path(instance, filename):
    return f"vehicle_photos/{instance.vehicle_id}/{filename}"


class VehiclePhoto(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to=vehicle_photo_path)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_vehicle_photos",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"Photo for {self.vehicle}"


class MileageLog(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="mileage_logs",
    )
    km = models.PositiveIntegerField()
    recorded_at = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="mileage_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.vehicle} — {self.km} km ({self.recorded_at})"


class TechnicalInspection(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspection_date = models.DateField()
    next_inspection_date = models.DateField(null=True, blank=True)
    report = models.FileField(
        upload_to="vehicles/inspections/",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_inspections",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inspection_date"]

    def __str__(self) -> str:
        return f"{self.vehicle} — inspection {self.inspection_date}"
