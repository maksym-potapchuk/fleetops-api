import json
import os
from pathlib import Path
import re

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from fleet_management.models import EquipmentDefaultItem
from fleet_management.services import grant_equipment_to_vehicle
from vehicle.constants import VehicleStatus
from vehicle.models import Vehicle, VehiclePhoto

DEFAULT_EQUIPMENT = [
    "Вогнегасник",
    "Аптечка",
    "Трикутник",
    "Жилет",
    "Буксирувальний трос",
    "Запасне колесо",
    "Домкрат",
]

TRELLO_LIST_TO_STATUS = {
    "Сервіс": VehicleStatus.SERVICE,
    "Фокус": VehicleStatus.FOCUS,
    "Встановлення Газу": VehicleStatus.GAS_INSTALL,
    "Хімчистка": VehicleStatus.CLEANING,
    "Підготовка до віддачі": VehicleStatus.PRE_DELIVERY,
    "Готова до здачі": VehicleStatus.READY,
    "Оренда": VehicleStatus.RENT,
    "Лізинг": VehicleStatus.LEASING,
    "Треба зглосити продажу": VehicleStatus.SELLING,
    "Продано": VehicleStatus.SOLD,
}

# {car_number} {manufacturer} {model...} {year} Vin: {vin}
RE_WITH_PLATE = re.compile(
    r"^(?P<car_number>[A-Z0-9]{5,10})\s+"
    r"(?P<manufacturer>\S+)\s+"
    r"(?P<model>.+?)\s+"
    r"(?P<year>\d{4})\s+"
    r"Vin:\s*(?P<vin>[A-Z0-9]{17})$",
    re.IGNORECASE,
)

# {manufacturer} {model...} {year} Vin: {vin}  (no plate)
RE_NO_PLATE = re.compile(
    r"^(?P<manufacturer>\S+)\s+"
    r"(?P<model>.+?)\s+"
    r"(?P<year>\d{4})\s+"
    r"Vin:\s*(?P<vin>[A-Z0-9]{17})$",
    re.IGNORECASE,
)

# edge case: {car_number} {year} {manufacturer} {model} Vin: {vin}
RE_YEAR_BEFORE_MAKE = re.compile(
    r"^(?P<car_number>[A-Z0-9]{5,10})\s+"
    r"(?P<year>\d{4})\s+"
    r"(?P<manufacturer>\S+)\s+"
    r"(?P<model>.+?)\s+"
    r"Vin:\s*(?P<vin>[A-Z0-9]{17})$",
    re.IGNORECASE,
)


def parse_card_name(name):
    """Parse Trello card name into vehicle fields. Returns dict or None."""
    for pattern in (RE_WITH_PLATE, RE_YEAR_BEFORE_MAKE, RE_NO_PLATE):
        m = pattern.match(name.strip())
        if m:
            d = m.groupdict()
            d["year"] = int(d["year"])
            d.setdefault("car_number", "")
            d["model"] = d["model"].strip()
            d["vin"] = d["vin"].upper()
            return d
    return None


def ensure_default_equipment(stdout):
    """Create default equipment items if they don't exist."""
    if not EquipmentDefaultItem.objects.exists():
        EquipmentDefaultItem.objects.bulk_create(
            [EquipmentDefaultItem(equipment=name) for name in DEFAULT_EQUIPMENT],
            ignore_conflicts=True,
        )
        stdout.write(f"  Created {len(DEFAULT_EQUIPMENT)} default equipment items")


class Command(BaseCommand):
    help = "Import vehicles from Trello export JSON into the database with photos to S3/media."

    def add_arguments(self, parser):
        parser.add_argument(
            "--list", default="", help="Trello list name (e.g. 'Сервіс')"
        )
        parser.add_argument(
            "--list-index",
            type=int,
            default=None,
            help="Trello list index (0-based, use instead of --list on Windows)",
        )
        parser.add_argument(
            "--json", default="trello_export.json", help="Path to trello_export.json"
        )
        parser.add_argument(
            "--photos", default="trello_photos", help="Path to trello_photos/ dir"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Preview without writing to DB/S3"
        )
        parser.add_argument(
            "--show-lists",
            action="store_true",
            help="Show available lists with indices and exit",
        )

    def handle(self, *args, **options):
        json_path = options["json"]
        photos_dir = Path(options["photos"])
        dry_run = options["dry_run"]

        if not os.path.exists(json_path):
            self.stderr.write(self.style.ERROR(f"File not found: {json_path}"))
            return

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        all_lists = data.get("lists", [])

        if options["show_lists"]:
            self.stdout.write("\nAvailable lists:")
            for i, lst in enumerate(all_lists):
                status = TRELLO_LIST_TO_STATUS.get(lst["name"], "—")
                self.stdout.write(f"  {i}: {lst['name']} → {status}")
            self.stdout.write("\nUsage: --list-index <number>")
            return

        # Resolve list name: by index or by name
        list_index = options["list_index"]
        list_name = options["list"]

        if list_index is not None:
            if list_index < 0 or list_index >= len(all_lists):
                self.stderr.write(
                    self.style.ERROR(
                        f"Index {list_index} out of range. Use --show-lists to see available lists."
                    )
                )
                return
            list_name = all_lists[list_index]["name"]
        elif not list_name:
            self.stderr.write(
                self.style.ERROR(
                    "Provide --list or --list-index. Use --show-lists to see options."
                )
            )
            return

        # Find the target list
        target_list = None
        for lst in all_lists:
            if lst["name"] == list_name:
                target_list = lst
                break

        if not target_list:
            available = [f"  {i}: {lst['name']}" for i, lst in enumerate(all_lists)]
            self.stderr.write(
                self.style.ERROR(
                    f"List '{list_name}' not found. Available:\n" + "\n".join(available)
                )
            )
            return

        status = TRELLO_LIST_TO_STATUS.get(list_name)
        if not status:
            self.stderr.write(self.style.ERROR(f"No status mapping for '{list_name}'"))
            return

        cards = target_list.get("cards", [])
        self.stdout.write(f"\nList: {list_name} → status: {status}")
        self.stdout.write(f"Cards: {len(cards)}\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made\n"))

        # Ensure default equipment items exist
        if not dry_run:
            ensure_default_equipment(self.stdout)

        report = {
            "list": list_name,
            "status": status,
            "imported": 0,
            "skipped": 0,
            "photos_uploaded": 0,
            "skipped_cards": [],
        }

        for card in cards:
            name = card["name"]
            parsed = parse_card_name(name)

            if not parsed:
                self.stdout.write(self.style.WARNING(f"  SKIP (parse failed): {name}"))
                report["skipped"] += 1
                report["skipped_cards"].append({"name": name, "reason": "parse_failed"})
                continue

            if not parsed["car_number"]:
                self.stdout.write(self.style.WARNING(f"  SKIP (no car_number): {name}"))
                report["skipped"] += 1
                report["skipped_cards"].append(
                    {"name": name, "reason": "missing car_number"}
                )
                continue

            vin = parsed["vin"]

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {parsed['car_number']} | {parsed['manufacturer']} {parsed['model']} "
                    f"{parsed['year']} | VIN: {vin} | photos: {len(card.get('attachments', []))}"
                )
                report["imported"] += 1
                continue

            # Create or get vehicle
            vehicle, created = Vehicle.objects.get_or_create(
                vin_number=vin,
                defaults={
                    "car_number": parsed["car_number"],
                    "manufacturer": parsed["manufacturer"],
                    "model": parsed["model"],
                    "year": parsed["year"],
                    "cost": 0,
                    "color": "#FFFFFF",
                    "initial_km": 0,
                    "status": status,
                },
            )

            if created:
                grant_equipment_to_vehicle(vehicle.id)

                self.stdout.write(
                    self.style.SUCCESS(f"  CREATED: {vehicle.car_number} ({vin})")
                )
                report["imported"] += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f"  EXISTS: {vehicle.car_number} ({vin})")
                )
                report["skipped"] += 1
                report["skipped_cards"].append(
                    {"name": name, "reason": "duplicate vin_number"}
                )
                continue

            # Upload photos
            attachments = card.get("attachments", [])
            # Cover photo first
            attachments.sort(key=lambda a: not a.get("is_cover", False))

            existing_photos = VehiclePhoto.objects.filter(vehicle=vehicle).count()
            for att in attachments:
                if existing_photos >= 10:
                    break

                local_path = att.get("local_path", "")
                if not local_path or not os.path.exists(local_path):
                    # Try constructing path from photos_dir
                    safe_name = parsed["car_number"]
                    safe_name = "".join(
                        c if c.isalnum() or c in "-_" else "_" for c in safe_name
                    )
                    local_path = str(photos_dir / safe_name / att.get("name", ""))
                    if not os.path.exists(local_path):
                        continue

                with open(local_path, "rb") as img_file:
                    photo = VehiclePhoto(vehicle=vehicle)
                    photo.image.save(
                        att["name"], ContentFile(img_file.read()), save=True
                    )
                    report["photos_uploaded"] += 1
                    existing_photos += 1

            if card.get("description"):
                self.stdout.write(f"    description: {card['description'][:80]}...")

        # Save report
        report_path = "import_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"  Imported:     {report['imported']}")
        self.stdout.write(f"  Skipped:      {report['skipped']}")
        self.stdout.write(f"  Photos:       {report['photos_uploaded']}")
        self.stdout.write(f"  Report:       {report_path}")
        self.stdout.write(f"{'=' * 50}\n")
