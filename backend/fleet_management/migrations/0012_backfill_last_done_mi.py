"""
Backfill last_done_mi for vehicles using miles.

For each regulation entry linked to a vehicle with distance_unit='mi',
compute last_done_mi = round(last_done_km * 0.621371) from the stored km.
This may be ±1 from the original user input (already lost to rounding),
but prevents further drift on future edits.
"""

from django.db import migrations

KM_TO_MI = 0.621371


def backfill_mi(apps, schema_editor):
    Vehicle = apps.get_model("vehicle", "Vehicle")
    Entry = apps.get_model("fleet_management", "FleetVehicleRegulationEntry")

    mi_vehicle_ids = set(
        Vehicle.objects.filter(distance_unit="mi").values_list("id", flat=True)
    )
    if not mi_vehicle_ids:
        return

    entries = Entry.objects.filter(
        regulation__vehicle_id__in=mi_vehicle_ids,
        last_done_mi__isnull=True,
    )

    to_update = []
    for entry in entries:
        entry.last_done_mi = round(entry.last_done_km * KM_TO_MI)
        to_update.append(entry)

    if to_update:
        Entry.objects.bulk_update(to_update, ["last_done_mi"], batch_size=500)


def reverse_mi(apps, schema_editor):
    Entry = apps.get_model("fleet_management", "FleetVehicleRegulationEntry")
    Entry.objects.filter(last_done_mi__isnull=False).update(last_done_mi=None)


class Migration(migrations.Migration):

    dependencies = [
        ("fleet_management", "0011_entry_last_done_mi"),
        ("vehicle", "0012_vehicle_distance_unit"),
    ]

    operations = [
        migrations.RunPython(backfill_mi, reverse_mi),
    ]
