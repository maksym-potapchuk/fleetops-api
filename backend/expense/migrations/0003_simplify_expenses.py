# Generated manually — simplify expense detail models

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0002_default_categories"),
        ("fleet_management", "0001_initial"),
    ]

    operations = [
        # ── Remove InsuranceExpenseDetail entirely ──
        migrations.DeleteModel(name="InsuranceExpenseDetail"),
        # ── Simplify FuelExpenseDetail: drop price_per_liter, gas_station, odometer_km ──
        migrations.RemoveField(model_name="fuelexpensedetail", name="price_per_liter"),
        migrations.RemoveField(model_name="fuelexpensedetail", name="gas_station"),
        migrations.RemoveField(model_name="fuelexpensedetail", name="odometer_km"),
        # ── Refactor ServiceExpenseDetail: drop old text fields, add FK ──
        migrations.RemoveField(model_name="serviceexpensedetail", name="service_type"),
        migrations.RemoveField(
            model_name="serviceexpensedetail", name="invoice_number"
        ),
        migrations.RemoveField(model_name="serviceexpensedetail", name="workshop_name"),
        migrations.RemoveField(model_name="serviceexpensedetail", name="odometer_km"),
        migrations.AddField(
            model_name="serviceexpensedetail",
            name="service",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expense_details",
                to="fleet_management.fleetservice",
            ),
        ),
        # ── Create ServiceItem ──
        migrations.CreateModel(
            name="ServiceItem",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "price",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                (
                    "expense",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_items",
                        to="expense.expense",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
