# Generated manually — deactivate INSURANCE category

from django.db import migrations


def deactivate_insurance(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.filter(code="INSURANCE").update(is_active=False)


def reactivate_insurance(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.filter(code="INSURANCE").update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0003_simplify_expenses"),
    ]

    operations = [
        migrations.RunPython(deactivate_insurance, reactivate_insurance),
    ]
