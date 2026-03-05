# create_vehicle_reg_basic_schema.py

from django.core.management.base import BaseCommand

from fleet_management.models import (
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
)

DEFAULT_SERVICE_SCHEMA = {
    "regulation_name": "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ",
    "regulation_name_pl": "REGULAMIN SERWISOWY",
    "regulation_name_uk": "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ",
    "services": [
        {
            "name": "Заміна моторного масла та масляного фільтра",
            "name_pl": "Wymiana oleju silnikowego i filtra oleju",
            "name_uk": "Заміна моторного масла та масляного фільтра",
            "interval_km": 10000,
            "notify_before_km": 500,
        },
        {
            "name": "Заміна фільтра газової системи",
            "name_pl": "Wymiana filtra instalacji gazowej",
            "name_uk": "Заміна фільтра газової системи",
            "interval_km": 10000,
            "notify_before_km": 500,
        },
        {
            "name": "Заміна повітряного фільтра двигуна",
            "name_pl": "Wymiana filtra powietrza silnika",
            "name_uk": "Заміна повітряного фільтра двигуна",
            "interval_km": 20000,
            "notify_before_km": 1000,
        },
        {
            "name": "Заміна салонного фільтра",
            "name_pl": "Wymiana filtra kabinowego",
            "name_uk": "Заміна салонного фільтра",
            "interval_km": 20000,
            "notify_before_km": 1000,
        },
        {
            "name": "Перевірка стану підвіски",
            "name_pl": "Kontrola stanu zawieszenia",
            "name_uk": "Перевірка стану підвіски",
            "interval_km": 20000,
            "notify_before_km": 1000,
        },
        {
            "name": "Заміна гальмівної рідини",
            "name_pl": "Wymiana płynu hamulcowego",
            "name_uk": "Заміна гальмівної рідини",
            "interval_km": 30000,
            "notify_before_km": 2000,
        },
        {
            "name": "Заміна гальмівних колодок",
            "name_pl": "Wymiana klocków hamulcowych",
            "name_uk": "Заміна гальмівних колодок",
            "interval_km": 30000,
            "notify_before_km": 2000,
        },
        {
            "name": "Перевірка електросистеми та компонентів двигуна",
            "name_pl": "Kontrola układu elektrycznego i podzespołów silnika",
            "name_uk": "Перевірка електросистеми та компонентів двигуна",
            "interval_km": 20000,
            "notify_before_km": 1000,
        },
        {
            "name": "Заміна рідини гідропідсилювача керма",
            "name_pl": "Wymiana płynu wspomagania kierownicy",
            "name_uk": "Заміна рідини гідропідсилювача керма",
            "interval_km": 48000,
            "notify_before_km": 2000,
        },
        {
            "name": "Заміна охолоджуючої рідини",
            "name_pl": "Wymiana płynu chłodniczego",
            "name_uk": "Заміна охолоджуючої рідини",
            "interval_km": 60000,
            "notify_before_km": 3000,
        },
        {
            "name": "Заміна насоса охолодження",
            "name_pl": "Wymiana pompy wody",
            "name_uk": "Заміна насоса охолодження",
            "interval_km": 120000,
            "notify_before_km": 5000,
        },
        {
            "name": "Заміна масла коробки передач",
            "name_pl": "Wymiana oleju skrzyni biegów",
            "name_uk": "Заміна масла коробки передач",
            "interval_km": 72000,
            "notify_before_km": 3000,
        },
        {
            "name": "Заміна паливного фільтра",
            "name_pl": "Wymiana filtra paliwa",
            "name_uk": "Заміна паливного фільтра",
            "interval_km": 72000,
            "notify_before_km": 3000,
        },
    ],
}


class Command(BaseCommand):
    help = "Seeds the default vehicle regulation schema into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing default schema and recreate it",
        )

    def handle(self, *args, **options):
        title = DEFAULT_SERVICE_SCHEMA["regulation_name"]

        if options["force"]:
            deleted, _ = FleetVehicleRegulationSchema.objects.filter(
                title=title,
            ).delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted existing schema: {deleted} record(s)"),
            )

        schema, created = FleetVehicleRegulationSchema.objects.get_or_create(
            title=title,
            defaults={
                "title_pl": DEFAULT_SERVICE_SCHEMA["regulation_name_pl"],
                "title_uk": DEFAULT_SERVICE_SCHEMA["regulation_name_uk"],
                "is_default": True,
            },
        )

        if not created:
            self.stdout.write(
                self.style.WARNING(
                    f'Schema "{title}" already exists. Use --force to recreate it.',
                ),
            )
            return

        items = [
            FleetVehicleRegulationItem(
                schema=schema,
                title=service["name"],
                title_pl=service["name_pl"],
                title_uk=service["name_uk"],
                every_km=service["interval_km"],
                notify_before_km=service["notify_before_km"],
            )
            for service in DEFAULT_SERVICE_SCHEMA["services"]
        ]

        FleetVehicleRegulationItem.objects.bulk_create(items)

        self.stdout.write(
            self.style.SUCCESS(f'Created schema "{title}" with {len(items)} items.'),
        )
