from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0005_vehicle_color"),
    ]

    operations = [
        migrations.CreateModel(
            name="TechnicalInspection",
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
                    "report",
                    models.FileField(
                        blank=True, null=True, upload_to="vehicles/inspections/"
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inspections",
                        to="vehicle.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["-inspection_date"],
            },
        ),
    ]
