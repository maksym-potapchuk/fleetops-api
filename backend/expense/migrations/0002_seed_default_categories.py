from django.db import migrations


def create_default_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    defaults = [
        {
            "code": "FUEL",
            "name": "Пальне",
            "icon": "fuel",
            "color": "#F59E0B",
            "is_system": True,
            "order": 1,
        },
        {
            "code": "SERVICE",
            "name": "Сервіс",
            "icon": "wrench",
            "color": "#3B82F6",
            "is_system": True,
            "order": 2,
        },
        {
            "code": "PARTS",
            "name": "Запчастини",
            "icon": "package",
            "color": "#8B5CF6",
            "is_system": True,
            "order": 3,
        },
        {
            "code": "INSURANCE",
            "name": "Страховка",
            "icon": "shield",
            "color": "#10B981",
            "is_system": True,
            "is_active": False,
            "order": 4,
        },
        {
            "code": "WASHING",
            "name": "Хімчистка",
            "icon": "droplets",
            "color": "#06B6D4",
            "is_system": True,
            "order": 5,
        },
        {
            "code": "INSPECTION",
            "name": "Technical Inspection",
            "is_system": True,
            "order": 6,
        },
        {
            "code": "FINES",
            "name": "Штрафи",
            "icon": "alert-triangle",
            "color": "#EF4444",
            "is_system": True,
            "order": 7,
        },
        {
            "code": "OTHER",
            "name": "Інше",
            "icon": "more-horizontal",
            "color": "#64748B",
            "is_system": True,
            "order": 8,
        },
        {
            "code": "ACCESSORIES",
            "name": "Аксесуари",
            "icon": "shopping-bag",
            "color": "#EC4899",
            "is_system": True,
            "order": 9,
        },
        {
            "code": "DOCUMENTS",
            "name": "Документи",
            "icon": "file-text",
            "color": "#6366F1",
            "is_system": True,
            "order": 10,
        },
    ]
    for d in defaults:
        ExpenseCategory.objects.create(**d)


def remove_default_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories),
    ]
