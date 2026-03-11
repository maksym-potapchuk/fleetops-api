from django.core.management.base import BaseCommand

from config import cache_utils
from fleet_management.constants import DEFAULT_EQUIPMENT, DEFAULT_REGULATION_SCHEMA
from fleet_management.models import (
    EquipmentDefaultItem,
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
)


class Command(BaseCommand):
    help = "Seeds the default regulation schema and equipment into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing default schema and recreate it",
        )

    def _seed_regulation(self, force: bool) -> None:
        schema_data = DEFAULT_REGULATION_SCHEMA
        title = schema_data["title"]

        if force:
            deleted, _ = FleetVehicleRegulationSchema.objects.filter(
                title=title,
            ).delete()
            if deleted:
                cache_utils.invalidate_schema()
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted existing schema: {deleted} record(s)",
                ),
            )

        schema, created = FleetVehicleRegulationSchema.objects.get_or_create(
            title=title,
            defaults={
                "title_pl": schema_data["title_pl"],
                "title_uk": schema_data["title_uk"],
                "title_en": schema_data.get("title_en", ""),
                "is_default": True,
            },
        )

        if not created and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Schema "{title}" already exists. Use --force to recreate.',
                ),
            )
            return

        items = [
            FleetVehicleRegulationItem(
                schema=schema,
                title=item["title"],
                title_pl=item["title_pl"],
                title_uk=item["title_uk"],
                title_en=item.get("title_en", ""),
                every_km=item["every_km"],
                notify_before_km=item["notify_before_km"],
            )
            for item in schema_data["items"]
        ]
        FleetVehicleRegulationItem.objects.bulk_create(items)
        cache_utils.invalidate_schema()

        self.stdout.write(
            self.style.SUCCESS(
                f'Created schema "{title}" with {len(items)} items.',
            ),
        )

    def _seed_equipment(self) -> None:
        existing = set(
            EquipmentDefaultItem.objects.values_list("equipment", flat=True),
        )
        new_items = [
            EquipmentDefaultItem(equipment=name)
            for name in DEFAULT_EQUIPMENT
            if name not in existing
        ]

        if new_items:
            EquipmentDefaultItem.objects.bulk_create(new_items)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(new_items)} equipment items.",
                ),
            )
        else:
            self.stdout.write("All equipment items already exist.")

    def handle(self, *args, **options):
        self._seed_regulation(force=options["force"])
        self._seed_equipment()
