import uuid

from django.db import models


class ManufacturerChoices(models.TextChoices):
    TOYOTA = "Toyota", "Toyota"
    FORD = "Ford", "Ford"
    HONDA = "Honda", "Honda"
    CHEVROLET = "Chevrolet", "Chevrolet"
    BMW = "BMW", "BMW"
    LEXUS = "Lexus", "Lexus"
    AUDI = "Audi", "Audi"


class VehicleStatus(models.TextChoices):
    CTO = "CTO", "CTO"
    FOCUS = "FOCUS", "Focus"
    CLEANING = "CLEANING", "Cleaning"
    PREPARATION = "PREPARATION", "Preparation"
    READY = "READY", "Ready"
    LEASING = "LEASING", "Leasing"
    RENT = "RENT", "Rent"
    SELLING = "SELLING", "Selling"
    SOLD = "SOLD", "Sold"


class Vehicle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.CharField(max_length=50)
    manufacturer = models.CharField(max_length=50, choices=ManufacturerChoices.choices)
    year = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    vin_number = models.CharField(max_length=17, unique=True)
    car_number = models.CharField(max_length=10, unique=True)
    initial_km = models.PositiveIntegerField(default=0)
    is_selected = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=VehicleStatus.choices,
        default=VehicleStatus.PREPARATION,
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.PROTECT,
        related_name="vehicle_driver",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.car_number} ({self.manufacturer} {self.model})"


class VehicleDriverHistory(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="vehicle_drivers",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.CASCADE,
        related_name="driver_vehicles",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.vehicle} ← {self.driver}"


class VehiclePhoto(models.Model):
    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="vehicles/photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"Photo for {self.vehicle}"


class VehicleOwnerHistory(models.Model):
    """Tracks who owns the vehicle and under what agreement."""

    vehicle = models.ForeignKey(
        "vehicle.Vehicle",
        on_delete=models.CASCADE,
        related_name="owner_history",
    )
    driver = models.ForeignKey(
        "driver.Driver",
        on_delete=models.PROTECT,
        related_name="owned_vehicles",
    )
    agreement_number = models.CharField(max_length=100, blank=True)
    acquired_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-acquired_at"]

    def __str__(self) -> str:
        return f"{self.vehicle} ← {self.driver}"
