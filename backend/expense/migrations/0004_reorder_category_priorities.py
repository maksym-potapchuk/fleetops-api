from django.db import migrations


NEW_ORDER = {
    "FUEL": 1,
    "DOCUMENTS": 2,
    "OTHER": 3,
    "PARTS": 4,
    "WASHING": 5,
    "INSPECTION": 6,
    "ACCESSORIES": 7,
    "FINES": 8,
    "SERVICE": 9,
}


def reorder_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    for code, order in NEW_ORDER.items():
        ExpenseCategory.objects.filter(code=code).update(order=order)


def reverse_order(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    old_order = {
        "FUEL": 1,
        "SERVICE": 2,
        "PARTS": 3,
        "WASHING": 5,
        "INSPECTION": 6,
        "FINES": 7,
        "OTHER": 8,
        "ACCESSORIES": 9,
        "DOCUMENTS": 10,
    }
    for code, order in old_order.items():
        ExpenseCategory.objects.filter(code=code).update(order=order)


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0003_alter_expense_expense_date"),
    ]

    operations = [
        migrations.RunPython(reorder_categories, reverse_order),
    ]
