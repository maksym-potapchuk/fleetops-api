from django.db import migrations

SCHEMA_TITLE = "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ"
SCHEMA_TITLE_PL = "REGULAMIN SERWISOWY"
SCHEMA_TITLE_UK = "РЕГЛАМЕНТ ОБСЛУГОВУВАННЯ"

DEFAULT_ITEMS = [
    # (title, title_pl, title_uk, every_km, notify_before_km)
    ("Заміна моторного масла та масляного фільтра", "Wymiana oleju silnikowego i filtra oleju", "Заміна моторного масла та масляного фільтра", 10_000, 500),
    ("Заміна фільтра газової системи", "Wymiana filtra instalacji gazowej", "Заміна фільтра газової системи", 10_000, 500),
    ("Заміна повітряного фільтра двигуна", "Wymiana filtra powietrza silnika", "Заміна повітряного фільтра двигуна", 20_000, 1_000),
    ("Заміна салонного фільтра", "Wymiana filtra kabinowego", "Заміна салонного фільтра", 20_000, 1_000),
    ("Перевірка стану підвіски", "Kontrola stanu zawieszenia", "Перевірка стану підвіски", 20_000, 1_000),
    ("Заміна гальмівної рідини", "Wymiana płynu hamulcowego", "Заміна гальмівної рідини", 30_000, 2_000),
    ("Заміна гальмівних колодок", "Wymiana klocków hamulcowych", "Заміна гальмівних колодок", 30_000, 2_000),
    ("Перевірка електросистеми та компонентів двигуна", "Kontrola układu elektrycznego i podzespołów silnika", "Перевірка електросистеми та компонентів двигуна", 20_000, 1_000),
    ("Заміна рідини гідропідсилювача керма", "Wymiana płynu wspomagania kierownicy", "Заміна рідини гідропідсилювача керма", 48_000, 2_000),
    ("Заміна охолоджуючої рідини", "Wymiana płynu chłodniczego", "Заміна охолоджуючої рідини", 60_000, 3_000),
    ("Заміна насоса охолодження", "Wymiana pompy wody", "Заміна насоса охолодження", 120_000, 5_000),
    ("Заміна масла коробки передач", "Wymiana oleju skrzyni biegów", "Заміна масла коробки передач", 72_000, 3_000),
    ("Заміна паливного фільтра", "Wymiana filtra paliwa", "Заміна паливного фільтра", 72_000, 3_000),
]


def forward(apps, schema_editor):
    Schema = apps.get_model("fleet_management", "FleetVehicleRegulationSchema")
    Item = apps.get_model("fleet_management", "FleetVehicleRegulationItem")

    # Remove old "Базовий регламент" with its items (cascade)
    Schema.objects.filter(title="Базовий регламент").delete()

    # Remove tech inspection item if it exists anywhere
    Item.objects.filter(title="Przegląd techniczny (OC)").delete()

    # Ensure default schema exists
    if not Schema.objects.filter(is_default=True).exists():
        schema = Schema.objects.create(
            title=SCHEMA_TITLE,
            title_pl=SCHEMA_TITLE_PL,
            title_uk=SCHEMA_TITLE_UK,
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


def backward(apps, schema_editor):
    Schema = apps.get_model("fleet_management", "FleetVehicleRegulationSchema")
    Schema.objects.filter(title=SCHEMA_TITLE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0004_fleetservice_address"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
