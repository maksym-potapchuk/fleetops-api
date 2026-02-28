from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from fleet_management.models import (
    FleetVehicleRegulation,
    FleetVehicleRegulationEntry,
    FleetVehicleRegulationSchema,
)
from vehicle.models import Vehicle


class Command(BaseCommand):
    help = "Show regulation plan for a vehicle by car number (e.g. AA6601BB). Use: make show-regulation CAR=AA6601BB"

    def add_arguments(self, parser):
        parser.add_argument(
            "car_number",
            nargs="?",
            type=str,
            help="Car number (e.g. AA6601BB). Or set CAR= in make.",
        )
        parser.add_argument(
            "--car",
            type=str,
            dest="car",
            help="Same as positional car_number (for make CAR=...).",
        )

    def handle(self, *args, **options):
        car_number = options.get("car_number") or options.get("car")
        if not car_number:
            self.stdout.write(
                self.style.ERROR(
                    "Give car number: python manage.py show_regulation_plan AA6601BB "
                    "or make show-regulation CAR=AA6601BB"
                )
            )
            return

        vehicle = Vehicle.objects.filter(car_number=car_number).first()
        if not vehicle:
            self.stdout.write(
                self.style.ERROR(f"Vehicle with car_number '{car_number}' not found.")
            )
            return

        regulation = (
            FleetVehicleRegulation.objects.filter(vehicle_id=vehicle.id)
            .prefetch_related(
                Prefetch(
                    "entries",
                    queryset=FleetVehicleRegulationEntry.objects.select_related("item"),
                )
            )
            .first()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Регламент для авто {car_number} (vehicle_id={vehicle.id})"
            )
        )
        self.stdout.write("")

        if regulation:
            for entry in regulation.entries.all():
                item = entry.item
                title = (item.title_uk or item.title).strip() or item.title
                next_km = entry.last_done_km + item.every_km
                self.stdout.write(
                    f"  {title}: кожні {item.every_km} км, "
                    f"останній раз {entry.last_done_km} км, наступний {next_km} км"
                )
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(f"Схема: {regulation.schema.title} (assigned)")
            )
            return

        default_schema = (
            FleetVehicleRegulationSchema.objects.filter(is_default=True)
            .prefetch_related("items")
            .first()
        )
        if not default_schema:
            self.stdout.write(
                self.style.WARNING(
                    "No regulation assigned and no default schema. Run create-reg-schema."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "Регламент для цього авто не призначено. Показую пункти дефолтної схеми (без пробігів):"
            )
        )
        for item in default_schema.items.all():
            title = (item.title_uk or item.title).strip() or item.title
            self.stdout.write(f"  {title}: кожні {item.every_km} км")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Схема: {default_schema.title}. Щоб призначити авто — використайте API regulation/<vehicle_pk>/assign/"
            )
        )
