"""
Assign default regulation schema to a vehicle by car number.
Fills regulation so the bot and API can show the plan.
Use: make assign-regulation CAR=AA6601BB
"""
from django.core.management.base import BaseCommand

from fleet_management.models import FleetVehicleRegulationSchema
from fleet_management.services import assign_regulation_to_vehicle
from vehicle.models import Vehicle


class Command(BaseCommand):
    help = "Assign default regulation schema to vehicle by car number. Use: make assign-regulation CAR=AA6601BB"

    def add_arguments(self, parser):
        parser.add_argument(
            "car_number",
            nargs="?",
            type=str,
            help="Car number (e.g. AA6601BB)",
        )
        parser.add_argument(
            "--car",
            type=str,
            dest="car",
            help="Car number (for make CAR=...).",
        )

    def handle(self, *args, **options):
        car_number = options.get("car_number") or options.get("car")
        if not car_number:
            self.stdout.write(
                self.style.ERROR(
                    "Give car number: python manage.py assign_regulation AA6601BB "
                    "or make assign-regulation CAR=AA6601BB"
                )
            )
            return

        vehicle = Vehicle.objects.filter(car_number=car_number).first()
        if not vehicle:
            self.stdout.write(
                self.style.ERROR(f"Vehicle with car_number '{car_number}' not found.")
            )
            return

        schema = FleetVehicleRegulationSchema.objects.filter(is_default=True).prefetch_related("items").first()
        if not schema:
            self.stdout.write(
                self.style.ERROR("No default regulation schema. Run: make create-reg-schema")
            )
            return

        initial_km = getattr(vehicle, "initial_km", 0) or 0
        entries_data = [
            {"item_id": item.id, "last_done_km": initial_km}
            for item in schema.items.all()
        ]

        try:
            result = assign_regulation_to_vehicle(
                vehicle_pk=vehicle.id,
                schema_id=schema.id,
                entries_data=entries_data,
                user=None,
            )
        except ValueError as e:
            self.stdout.write(
                self.style.WARNING(f"Регламент вже призначено для цього авто: {e}")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Регламент для {car_number} заповнено: схема «{result['schema']}», "
                f"пунктів: {result['entries_created']}, початковий пробіг: {initial_km} км."
            )
        )
