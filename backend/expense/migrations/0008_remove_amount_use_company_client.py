"""
Migration: remove `amount` field, make `company_amount` non-nullable with default=0.
Existing data: copy amount → company_amount where company_amount is NULL (COMPANY payer_type).
"""

from django.db import migrations, models


def populate_company_amount(apps, schema_editor):
    """For existing expenses where company_amount is NULL, copy amount to company_amount."""
    Expense = apps.get_model("expense", "Expense")
    Expense.objects.filter(company_amount__isnull=True).update(
        company_amount=models.F("amount")
    )


def reverse_populate(apps, schema_editor):
    """Reverse: copy company_amount + client_amount back to amount."""
    from django.db.models.functions import Coalesce

    Expense = apps.get_model("expense", "Expense")
    Expense.objects.all().update(
        amount=models.F("company_amount") + Coalesce("client_amount", 0)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("expense", "0007_fuel_remove_liters_req_and_fuel_types_json"),
    ]

    operations = [
        # 1. Copy amount → company_amount for COMPANY payer_type records
        migrations.RunPython(populate_company_amount, reverse_populate),
        # 2. Make company_amount non-nullable with default=0
        migrations.AlterField(
            model_name="expense",
            name="company_amount",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10
            ),
        ),
        # 3. Remove the amount column
        migrations.RemoveField(
            model_name="expense",
            name="amount",
        ),
    ]
