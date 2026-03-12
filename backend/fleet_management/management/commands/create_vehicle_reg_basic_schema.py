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
            help="Update existing schema items in-place (safe for prod)",
        )

    def _seed_regulation(self, force: bool) -> None:
        schema_data = DEFAULT_REGULATION_SCHEMA
        title = schema_data["title"]

        schema, created = FleetVehicleRegulationSchema.objects.get_or_create(
            title=title,
            defaults={
                "title_pl": schema_data["title_pl"],
                "title_uk": schema_data["title_uk"],
                "title_en": schema_data.get("title_en", ""),
                "is_default": True,
            },
        )

        if created:
            items = [
                FleetVehicleRegulationItem(
                    schema=schema,
                    title=item["title"],
                    title_pl=item["title_pl"],
                    title_uk=item["title_uk"],
                    title_en=item.get("title_en", ""),
                    every_km=item["every_km"],
                    every_mi=item.get("every_mi"),
                    notify_before_km=item["notify_before_km"],
                    notify_before_mi=item.get("notify_before_mi"),
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
            return

        if not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Schema "{title}" already exists. Use --force to update.',
                ),
            )
            return

        # --force: update schema translations
        schema.title_pl = schema_data["title_pl"]
        schema.title_uk = schema_data["title_uk"]
        schema.title_en = schema_data.get("title_en", "")
        schema.save(update_fields=["title_pl", "title_uk", "title_en"])

        # Upsert items: update existing, create missing
        updated, new = 0, 0
        for item_data in schema_data["items"]:
            fields = {
                "title_pl": item_data["title_pl"],
                "title_uk": item_data["title_uk"],
                "title_en": item_data.get("title_en", ""),
                "every_km": item_data["every_km"],
                "every_mi": item_data.get("every_mi"),
                "notify_before_km": item_data["notify_before_km"],
                "notify_before_mi": item_data.get("notify_before_mi"),
            }
            item, was_created = FleetVehicleRegulationItem.objects.get_or_create(
                schema=schema,
                title=item_data["title"],
                defaults=fields,
            )
            if was_created:
                new += 1
            else:
                for attr, val in fields.items():
                    setattr(item, attr, val)
                item.save(update_fields=list(fields.keys()))
                updated += 1

        cache_utils.invalidate_schema()
        self.stdout.write(
            self.style.SUCCESS(
                f'Updated schema "{title}": {updated} items updated, {new} new items created.',
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
