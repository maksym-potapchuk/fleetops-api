# Generated manually — add INSPECTION category and detail model

import django.db.models.deletion
from django.db import migrations, models


def create_inspection_category(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.get_or_create(
        code="INSPECTION",
        defaults={
            "name": "Technical Inspection",
            "is_system": True,
            "is_active": True,
            "order": 6,
        },
    )


def remove_inspection_category(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.filter(code="INSPECTION").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0004_deactivate_insurance"),
    ]

    operations = [
        migrations.CreateModel(
            name="InspectionExpenseDetail",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("inspection_date", models.DateField()),
                (
                    "official_cost",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                (
                    "additional_cost",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10),
                ),
                (
                    "expense",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inspection_detail",
                        to="expense.expense",
                    ),
                ),
            ],
            options={
                "verbose_name": "Inspection detail",
            },
        ),
        migrations.RunPython(
            create_inspection_category,
            remove_inspection_category,
        ),
    ]
