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

DEFAULT_SCHEMA_TITLE = "Базовий регламент"

DEFAULT_ITEMS = [
    # (title, title_pl, title_uk, every_km, notify_before_km)
    (
        "Zmiana oleju silnikowego",
        "Zmiana oleju silnikowego",
        "Заміна моторного масла",
        10_000,
        500,
    ),
    (
        "Wymiana filtra oleju",
        "Wymiana filtra oleju",
        "Заміна фільтра масла",
        10_000,
        500,
    ),
    (
        "Wymiana filtra powietrza",
        "Wymiana filtra powietrza",
        "Заміна повітряного фільтра",
        20_000,
        1_000,
    ),
    (
        "Wymiana filtra kabinowego",
        "Wymiana filtra kabinowego",
        "Заміна салонного фільтра",
        20_000,
        1_000,
    ),
    (
        "Wymiana filtra paliwa",
        "Wymiana filtra paliwa",
        "Заміна паливного фільтра",
        30_000,
        1_500,
    ),
    (
        "Kontrola klocków hamulcowych",
        "Kontrola klocków hamulcowych",
        "Перевірка гальмівних колодок",
        20_000,
        1_000,
    ),
    (
        "Wymiana płynu hamulcowego",
        "Wymiana płynu hamulcowego",
        "Заміна гальмівної рідини",
        40_000,
        2_000,
    ),
    (
        "Wymiana płynu chłodniczego",
        "Wymiana płynu chłodniczego",
        "Заміна охолоджуючої рідини",
        60_000,
        3_000,
    ),
    ("Kontrola rozrządu", "Kontrola rozrządu", "Перевірка ГРМ", 60_000, 3_000),
    (
        "Wymiana pasków klinowych",
        "Wymiana pasków klinowych",
        "Заміна клинових пасів",
        60_000,
        3_000,
    ),
    (
        "Kontrola zawieszenia",
        "Kontrola zawieszenia",
        "Перевірка підвіски",
        30_000,
        1_500,
    ),
    (
        "Przegląd techniczny (OC)",
        "Przegląd techniczny (OC)",
        "Технічний огляд",
        100_000,
        5_000,
    ),
]


def seed_equipment(apps, schema_editor):
    EquipmentDefaultItem = apps.get_model("fleet_management", "EquipmentDefaultItem")
    EquipmentDefaultItem.objects.bulk_create(
        [EquipmentDefaultItem(equipment=name) for name in DEFAULT_EQUIPMENT],
        ignore_conflicts=True,
    )


def remove_equipment(apps, schema_editor):
    EquipmentDefaultItem = apps.get_model("fleet_management", "EquipmentDefaultItem")
    EquipmentDefaultItem.objects.filter(equipment__in=DEFAULT_EQUIPMENT).delete()


def seed_regulation_schema(apps, schema_editor):
    Schema = apps.get_model("fleet_management", "FleetVehicleRegulationSchema")
    Item = apps.get_model("fleet_management", "FleetVehicleRegulationItem")

    if Schema.objects.filter(is_default=True).exists():
        return

    schema = Schema.objects.create(
        title=DEFAULT_SCHEMA_TITLE,
        title_pl="Podstawowy regulamin",
        title_uk="Базовий регламент",
        is_default=True,
        created_by=None,
    )

    Item.objects.bulk_create(
        [
            Item(
                schema=schema,
                title=title,
                title_pl=title_pl,
                title_uk=title_uk,
                every_km=every_km,
                notify_before_km=notify_before_km,
            )
            for title, title_pl, title_uk, every_km, notify_before_km in DEFAULT_ITEMS
        ]
    )


def remove_regulation_schema(apps, schema_editor):
    Schema = apps.get_model("fleet_management", "FleetVehicleRegulationSchema")
    Schema.objects.filter(title=DEFAULT_SCHEMA_TITLE, is_default=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_equipment, remove_equipment),
        migrations.RunPython(seed_regulation_schema, remove_regulation_schema),
    ]
