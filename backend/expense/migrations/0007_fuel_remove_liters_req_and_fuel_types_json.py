"""
Migration: make liters nullable, rename fuel_type → fuel_types (JSONField),
convert existing single values to list format.
"""

from django.db import migrations, models


def convert_fuel_type_to_list(apps, schema_editor):
    """Convert old fuel_type string values to fuel_types JSON list."""
    FuelExpenseDetail = apps.get_model("expense", "FuelExpenseDetail")
    for detail in FuelExpenseDetail.objects.all():
        old_value = detail.fuel_type or ""
        if old_value:
            detail.fuel_types = [old_value]
        else:
            detail.fuel_types = []
        detail.save(update_fields=["fuel_types"])


def convert_fuel_types_back(apps, schema_editor):
    """Reverse: take first element from list back to string."""
    FuelExpenseDetail = apps.get_model("expense", "FuelExpenseDetail")
    for detail in FuelExpenseDetail.objects.all():
        types_list = detail.fuel_types or []
        detail.fuel_type = types_list[0] if types_list else ""
        detail.save(update_fields=["fuel_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("expense", "0006_add_company_client_amounts"),
    ]

    operations = [
        # 1. Make liters nullable
        migrations.AlterField(
            model_name="fuelexpensedetail",
            name="liters",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True
            ),
        ),
        # 2. Add new fuel_types JSONField
        migrations.AddField(
            model_name="fuelexpensedetail",
            name="fuel_types",
            field=models.JSONField(
                default=list,
                help_text="List of fuel types, e.g. ['DIESEL', 'LPG']",
            ),
        ),
        # 3. Copy data from fuel_type → fuel_types
        migrations.RunPython(convert_fuel_type_to_list, convert_fuel_types_back),
        # 4. Remove old fuel_type column
        migrations.RemoveField(
            model_name="fuelexpensedetail",
            name="fuel_type",
        ),
    ]
