import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("vehicle", "0016_alter_vehicle_fuel_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleDocument",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("file", models.FileField(upload_to="vehicles/documents/")),
                (
                    "document_type",
                    models.CharField(
                        choices=[("photo", "Photo"), ("pdf", "PDF")],
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_vehicle_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="vehicle.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["document_type", "created_at"],
            },
        ),
    ]
