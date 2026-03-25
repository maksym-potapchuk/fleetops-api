import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from driver.models import Driver, DriverVehicleDeal
from vehicle.models import OwnerHistory, Vehicle, VehicleOwner


class Command(BaseCommand):
    help = "Assign a random driver to a random unassigned vehicle (or a specific one by --car)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--car",
            type=str,
            help="Car number to assign a driver to (otherwise picks random unassigned vehicle).",
        )

    def _sync_deal(self, vehicle, driver):
        """Sync DriverVehicleDeal (unmanaged table) so the API serializer sees the assignment."""
        deal_table_exists = DriverVehicleDeal.objects.filter(vehicle=vehicle).exists()
        if deal_table_exists:
            DriverVehicleDeal.objects.filter(vehicle=vehicle).update(driver=driver)
        else:
            deal_id = uuid.uuid4()
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO driver_vehicle_deal (id, driver_id, vehicle_id, deal_id) "
                    "VALUES (%s, %s, %s, %s)",
                    [str(uuid.uuid4()), str(driver.id), str(vehicle.id), str(deal_id)],
                )

    def handle(self, *args, **options):
        car_number = options.get("car")

        if car_number:
            vehicle = Vehicle.objects.filter(
                car_number=car_number, is_archived=False
            ).first()
            if not vehicle:
                raise CommandError(f"Vehicle with car number '{car_number}' not found.")
        else:
            assigned_vehicle_ids = VehicleOwner.objects.values_list(
                "vehicle_id", flat=True
            )
            vehicle = (
                Vehicle.objects.filter(is_archived=False)
                .exclude(id__in=assigned_vehicle_ids)
                .order_by("?")
                .first()
            )
            if not vehicle:
                raise CommandError("No unassigned vehicles available.")

        driver = Driver.objects.order_by("?").first()
        if not driver:
            raise CommandError("No drivers in the database.")

        existing = VehicleOwner.objects.filter(vehicle=vehicle).first()
        if existing:
            OwnerHistory.objects.create(
                vehicle=vehicle,
                driver=existing.driver,
                agreement_number=existing.agreement_number,
                assigned_at=existing.assigned_at,
                unassigned_at=timezone.now(),
                created_by=existing.created_by,
            )
            old_driver = existing.driver
            existing.driver = driver
            existing.agreement_number = ""
            existing.save(update_fields=["driver", "agreement_number"])

            if not VehicleOwner.objects.filter(driver=old_driver).exists():
                old_driver.has_vehicle = False
                old_driver.save(update_fields=["has_vehicle"])

            self.stdout.write(
                self.style.WARNING(
                    f"Reassigned {vehicle.car_number}: {old_driver} → {driver}"
                )
            )
        else:
            VehicleOwner.objects.create(vehicle=vehicle, driver=driver)

        self._sync_deal(vehicle, driver)

        driver.has_vehicle = True
        driver.save(update_fields=["has_vehicle"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Assigned driver {driver} ({driver.phone_number}) "
                f"to vehicle {vehicle.car_number} ({vehicle.manufacturer} {vehicle.model})"
            )
        )
