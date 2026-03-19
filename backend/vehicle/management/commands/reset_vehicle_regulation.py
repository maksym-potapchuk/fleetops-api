from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fleet_management.models import FleetVehicleRegulation
from vehicle.models import MileageLog, Vehicle


class Command(BaseCommand):
    help = "Reset mileage and regulation data for a vehicle by car number."

    def add_arguments(self, parser):
        parser.add_argument("car_number", type=str, help="Vehicle plate number (e.g. AA1234BB)")
        parser.add_argument("--force", action="store_true", help="Skip confirmation prompt.")

    @transaction.atomic
    def handle(self, *args, **options):
        car_number = options["car_number"].strip().upper()

        try:
            vehicle = Vehicle.objects.get(car_number__iexact=car_number)
        except Vehicle.DoesNotExist:
            raise CommandError(f"Vehicle with car_number '{car_number}' not found.")

        mileage_count = MileageLog.objects.filter(vehicle=vehicle).count()
        regulation_count = FleetVehicleRegulation.objects.filter(vehicle=vehicle).count()

        self.stdout.write(f"Vehicle: {vehicle}")
        self.stdout.write(f"  initial_km: {vehicle.initial_km}")
        self.stdout.write(f"  Mileage logs: {mileage_count}")
        self.stdout.write(f"  Regulations: {regulation_count}")

        if mileage_count == 0 and regulation_count == 0 and vehicle.initial_km == 0:
            self.stdout.write("Nothing to reset.")
            return

        if not options["force"]:
            confirm = input(
                "This will delete ALL mileage logs, regulations (with entries, history, notifications) "
                "and reset initial_km to 0. Type 'yes' to confirm: "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write("Aborted.")
                return

        # Delete mileage logs
        deleted_mileage, _ = MileageLog.objects.filter(vehicle=vehicle).delete()

        # Delete regulations (CASCADE deletes entries, history, notifications)
        deleted_reg, details = FleetVehicleRegulation.objects.filter(vehicle=vehicle).delete()

        # Reset initial_km
        old_km = vehicle.initial_km
        vehicle.initial_km = 0
        vehicle.save(update_fields=["initial_km"])

        self.stdout.write(self.style.SUCCESS(
            f"Done for {car_number}:\n"
            f"  initial_km: {old_km} → 0\n"
            f"  Mileage logs deleted: {deleted_mileage}\n"
            f"  Regulations deleted: {deleted_reg}\n"
            f"  Related objects: {details}"
        ))
