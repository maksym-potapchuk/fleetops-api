from django.db import migrations


DEFAULT_EQUIPMENT = [
    "Вогнегасник",
    "Аптечка",
    "Трикутник",
    "Жилет",
    "Буксирувальний трос",
    "Запасне колесо",
    "Домкрат",
]


def add_default_equipment(apps, schema_editor):
    EquipmentDefaultItem = apps.get_model("fleet_management", "EquipmentDefaultItem")
    EquipmentDefaultItem.objects.bulk_create(
        [EquipmentDefaultItem(equipment=name) for name in DEFAULT_EQUIPMENT],
        ignore_conflicts=True,
    )


def remove_default_equipment(apps, schema_editor):
    EquipmentDefaultItem = apps.get_model("fleet_management", "EquipmentDefaultItem")
    EquipmentDefaultItem.objects.filter(equipment__in=DEFAULT_EQUIPMENT).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0004_add_title_translations_to_regulation"),
    ]

    operations = [
        migrations.RunPython(add_default_equipment, remove_default_equipment),
    ]
