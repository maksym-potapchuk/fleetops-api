from django.core.management.base import BaseCommand

from driver.models import Driver
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle, VehicleOwner

DRIVER_PHONE = "+380663234712"
DEFAULT_FIRST_NAME = "Тест"
DEFAULT_LAST_NAME = "Водій"

# One vehicle per phone — unique VIN and car_number so command is re-runnable
VEHICLE_VIN = "1HGBH41JXMN109186"
VEHICLE_CAR_NUMBER = "AA6601BB"
VEHICLE_MODEL = "Camry"
VEHICLE_MANUFACTURER = ManufacturerChoices.TOYOTA
VEHICLE_YEAR = 2022
VEHICLE_COST = 35000.00
VEHICLE_INITIAL_KM = 0


class Command(BaseCommand):
    help = (
        "Creates a driver with phone +380663234712, creates a vehicle, "
        "and assigns the vehicle to that driver."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate driver/vehicle if they already exist (driver by phone, vehicle by VIN).",
        )

    def handle(self, *args, **options):
        force = options["force"]

        driver = Driver.objects.filter(phone_number=DRIVER_PHONE).first()
        if driver:
            if not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Driver with phone {DRIVER_PHONE} already exists: {driver}. "
                        "Use --force to recreate."
                    )
                )
                return
            self.stdout.write(self.style.WARNING(f"Updating existing driver: {driver}"))
        else:
            driver = Driver.objects.create(
                first_name=DEFAULT_FIRST_NAME,
                last_name=DEFAULT_LAST_NAME,
                phone_number=DRIVER_PHONE,
                has_vehicle=False,
                is_active_driver=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Created driver: {driver}"))

        vehicle = Vehicle.objects.filter(vin_number=VEHICLE_VIN).first()
        if vehicle:
            if not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Vehicle with VIN {VEHICLE_VIN} already exists: {vehicle}. "
                        "Use --force to reassign to driver."
                    )
                )
                return
            self.stdout.write(
                self.style.WARNING(f"Updating existing vehicle: {vehicle}")
            )
        else:
            vehicle = Vehicle.objects.create(
                model=VEHICLE_MODEL,
                manufacturer=VEHICLE_MANUFACTURER,
                year=VEHICLE_YEAR,
                cost=VEHICLE_COST,
                vin_number=VEHICLE_VIN,
                car_number=VEHICLE_CAR_NUMBER,
                initial_km=VEHICLE_INITIAL_KM,
                status=VehicleStatus.AUCTION,
            )
            self.stdout.write(self.style.SUCCESS(f"Created vehicle: {vehicle}"))

        # Assign vehicle to driver via VehicleOwner
        VehicleOwner.objects.update_or_create(
            vehicle=vehicle,
            defaults={"driver": driver},
        )
        driver.has_vehicle = True
        driver.save(update_fields=["has_vehicle"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Assigned vehicle {vehicle.car_number} to driver {driver} ({driver.phone_number})."
            )
        )
