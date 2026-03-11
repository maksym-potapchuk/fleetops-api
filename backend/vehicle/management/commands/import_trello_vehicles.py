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

# VIN pattern — always 17 alphanumeric chars
RE_VIN = re.compile(r"[A-Z0-9]{17}", re.IGNORECASE)
# Car plate — 5-10 alphanumeric, must contain both letters and digits
RE_PLATE = re.compile(r"^[A-Z0-9]{5,10}$", re.IGNORECASE)
# Year — 4 digits, 1990-2099
RE_YEAR = re.compile(r"\b(19[9]\d|20\d{2})\b")


def _looks_like_plate(token: str) -> bool:
    """Plate must have both letters and digits, 5-10 chars."""
    return bool(
        RE_PLATE.match(token)
        and re.search(r"[A-Z]", token, re.IGNORECASE)
        and re.search(r"\d", token)
    )


def parse_card_name(name):
    """Parse Trello card name into vehicle fields. Returns dict or None.

    Handles many Trello card naming styles:
    - Standard:  PLATE Manufacturer Model YEAR Vin: VIN
    - Vin;       PLATE Manufacturer Model YEAR Vin; VIN
    - No Vin:    PLATE Manufacturer Model YEAR VIN
    - No plate:  Manufacturer Model YEAR Vin: VIN
    - No year:   PLATE Manufacturer Model VIN
    - Reordered: PLATE YEAR Manufacturer Model Vin: VIN
    - Mixed:     Manufacturer Model YEAR PLATE, VIN:VIN
    """
    # Normalize: strip, remove commas, collapse whitespace
    text = name.strip().replace(",", " ")
    # Normalize Vin;/VIN:/Vin: → remove it (we detect VIN by pattern)
    text = re.sub(r"\bVin[;:]\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    # Extract VIN (17 alphanumeric)
    vin_match = RE_VIN.search(text)
    vin = vin_match.group(0).upper() if vin_match else None

    # Remove VIN from text for further parsing
    if vin_match:
        text = text[: vin_match.start()] + text[vin_match.end() :]
        text = text.strip()

    # Extract year
    year_match = RE_YEAR.search(text)
    year = int(year_match.group(0)) if year_match else None
    if year_match:
        text = text[: year_match.start()] + text[year_match.end() :]
        text = text.strip()

    # Split remaining tokens
    tokens = text.split()
    if not tokens:
        return None

    # Detect plate — first or last token that looks like a plate
    car_number = None
    if tokens and _looks_like_plate(tokens[0]):
        car_number = tokens.pop(0)
    elif tokens and _looks_like_plate(tokens[-1]):
        car_number = tokens.pop(-1)

    # Must have at least manufacturer
    if not tokens:
        return None

    # First remaining token = manufacturer, rest = model
    manufacturer = tokens[0]
    model = " ".join(tokens[1:]) if len(tokens) > 1 else ""

    # Must have at least manufacturer to be useful
    if not manufacturer:
        return None

    return {
        "car_number": car_number,
        "manufacturer": manufacturer,
        "model": model,
        "year": year,
        "vin": vin,
    }


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
            "--all",
            action="store_true",
            help="Import ALL lists that have a status mapping",
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
        parser.add_argument(
            "--reposition",
            action="store_true",
            help="Reposition existing vehicles to match Trello card order (no new imports)",
        )
        parser.add_argument(
            "--retry-skipped",
            action="store_true",
            help="Re-import only previously skipped cards from import_report.json",
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
            self.stdout.write("\nUsage: --list-index <number> or --all")
            return

        # ── --retry-skipped: re-import only previously skipped cards ──
        if options["retry_skipped"]:
            report_path = "import_report.json"
            if not os.path.exists(report_path):
                self.stderr.write(
                    self.style.ERROR(
                        f"{report_path} not found. Run a full import first."
                    )
                )
                return

            with open(report_path, encoding="utf-8") as f:
                prev_report = json.load(f)

            # Collect skipped card names per list
            skipped_by_list = {}
            lists_data = prev_report.get("lists", [prev_report])
            for lr in lists_data:
                for sc in lr.get("skipped_cards", []):
                    skipped_by_list.setdefault(lr["list"], set()).add(sc["name"])

            if not any(skipped_by_list.values()):
                self.stdout.write(self.style.SUCCESS("No skipped cards to retry."))
                return

            if not dry_run:
                ensure_default_equipment(self.stdout)

            total = {"imported": 0, "skipped": 0, "photos_uploaded": 0}

            for lst in all_lists:
                list_name = lst["name"]
                skipped_names = skipped_by_list.get(list_name)
                if not skipped_names:
                    continue

                status = TRELLO_LIST_TO_STATUS.get(list_name)
                if not status:
                    continue

                # Build a filtered list with only skipped cards
                filtered_list = {
                    "name": list_name,
                    "cards": [
                        c for c in lst.get("cards", []) if c["name"] in skipped_names
                    ],
                }

                self.stdout.write(
                    f"\nRetrying {len(filtered_list['cards'])} skipped cards "
                    f"from '{list_name}'"
                )

                report = self._import_list(filtered_list, status, photos_dir, dry_run)
                total["imported"] += report["imported"]
                total["skipped"] += report["skipped"]
                total["photos_uploaded"] += report["photos_uploaded"]

            self.stdout.write(f"\n{'=' * 50}")
            self.stdout.write(f"  Retry Imported:  {total['imported']}")
            self.stdout.write(f"  Still Skipped:   {total['skipped']}")
            self.stdout.write(f"  Photos:          {total['photos_uploaded']}")
            self.stdout.write(f"{'=' * 50}\n")
            return

        # ── --reposition: update status_position for existing vehicles ──
        if options["reposition"]:
            updated = 0
            for lst in all_lists:
                status = TRELLO_LIST_TO_STATUS.get(lst["name"])
                if not status:
                    continue
                cards = lst.get("cards", [])
                position = 1000
                for card in cards:
                    parsed = parse_card_name(card["name"])
                    if not parsed or not parsed["vin"]:
                        continue
                    count = Vehicle.objects.filter(vin_number=parsed["vin"]).update(
                        status_position=position
                    )
                    if count:
                        self.stdout.write(
                            f"  {parsed['car_number'] or parsed['vin']} → pos={position}"
                        )
                        updated += count
                    position += 1000
            self.stdout.write(self.style.SUCCESS(f"\nRepositioned {updated} vehicles."))
            return

        # ── --all: import every list with a status mapping ──
        if options["all"]:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("DRY RUN — no changes will be made\n")
                )
            if not dry_run:
                ensure_default_equipment(self.stdout)

            total = {"imported": 0, "skipped": 0, "photos_uploaded": 0}
            list_reports = []

            for lst in all_lists:
                status = TRELLO_LIST_TO_STATUS.get(lst["name"])
                if not status:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n  SKIP list '{lst['name']}' (no status mapping)"
                        )
                    )
                    continue

                report = self._import_list(lst, status, photos_dir, dry_run)
                list_reports.append(report)
                total["imported"] += report["imported"]
                total["skipped"] += report["skipped"]
                total["photos_uploaded"] += report["photos_uploaded"]

            # Save combined report
            combined = {"lists": list_reports, **total}
            report_path = "import_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(combined, f, ensure_ascii=False, indent=2)

            self.stdout.write(f"\n{'=' * 50}")
            self.stdout.write(f"  TOTAL Imported:  {total['imported']}")
            self.stdout.write(f"  TOTAL Skipped:   {total['skipped']}")
            self.stdout.write(f"  TOTAL Photos:    {total['photos_uploaded']}")
            self.stdout.write(f"  Report:          {report_path}")
            self.stdout.write(f"{'=' * 50}\n")
            return

        # ── Single list mode ──
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
                    "Provide --list, --list-index, or --all. Use --show-lists to see options."
                )
            )
            return

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

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made\n"))
        if not dry_run:
            ensure_default_equipment(self.stdout)

        report = self._import_list(target_list, status, photos_dir, dry_run)

        report_path = "import_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"  Imported:     {report['imported']}")
        self.stdout.write(f"  Skipped:      {report['skipped']}")
        self.stdout.write(f"  Photos:       {report['photos_uploaded']}")
        self.stdout.write(f"  Report:       {report_path}")
        self.stdout.write(f"{'=' * 50}\n")

    def _import_list(self, trello_list, status, photos_dir, dry_run):
        """Import all cards from a single Trello list. Returns report dict."""
        list_name = trello_list["name"]
        cards = trello_list.get("cards", [])

        self.stdout.write(f"\nList: {list_name} → status: {status}")
        self.stdout.write(f"Cards: {len(cards)}")

        report = {
            "list": list_name,
            "status": status,
            "imported": 0,
            "skipped": 0,
            "photos_uploaded": 0,
            "skipped_cards": [],
        }

        position = 1000
        for card in cards:
            name = card["name"]
            parsed = parse_card_name(name)

            if not parsed:
                self.stdout.write(self.style.WARNING(f"  SKIP (parse failed): {name}"))
                report["skipped"] += 1
                report["skipped_cards"].append({"name": name, "reason": "parse_failed"})
                continue

            vin = parsed["vin"]

            if not vin:
                self.stdout.write(self.style.WARNING(f"  SKIP (no VIN): {name}"))
                report["skipped"] += 1
                report["skipped_cards"].append({"name": name, "reason": "no_vin"})
                continue

            if dry_run:
                plate = parsed["car_number"] or "NO PLATE"
                self.stdout.write(
                    f"  [DRY] {plate} | {parsed['manufacturer']} {parsed['model']} "
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
                    "status_position": position,
                },
            )

            if created:
                grant_equipment_to_vehicle(vehicle.id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  CREATED: {vehicle.car_number or vin} ({vin}) pos={position}"
                    )
                )
                report["imported"] += 1
                position += 1000
            else:
                self.stdout.write(
                    self.style.WARNING(f"  EXISTS: {vehicle.car_number or vin} ({vin})")
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

            for att in attachments:
                local_path = att.get("local_path", "")
                if not local_path or not os.path.exists(local_path):
                    # Try constructing path from photos_dir
                    safe_name = parsed["car_number"] or parsed["vin"]
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

            if card.get("description"):
                self.stdout.write(f"    description: {card['description'][:80]}...")

        return report
