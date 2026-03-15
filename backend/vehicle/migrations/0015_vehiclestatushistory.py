from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("vehicle", "0014_alter_vehicle_fuel_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleStatusHistory",
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
                (
                    "old_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("AUCTION", "Auction Selection"),
                            ("FOCUS", "Focus"),
                            ("GAS_INSTALL", "Gas Installation"),
                            ("SERVICE", "Service"),
                            ("CLEANING", "Cleaning"),
                            ("PRE_DELIVERY", "Pre-delivery"),
                            ("READY", "Ready for Delivery"),
                            ("RENT", "Rent"),
                            ("LEASING", "Leasing"),
                            ("SELLING", "Report for Sale"),
                            ("SOLD", "Sold"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        choices=[
                            ("AUCTION", "Auction Selection"),
                            ("FOCUS", "Focus"),
                            ("GAS_INSTALL", "Gas Installation"),
                            ("SERVICE", "Service"),
                            ("CLEANING", "Cleaning"),
                            ("PRE_DELIVERY", "Pre-delivery"),
                            ("READY", "Ready for Delivery"),
                            ("RENT", "Rent"),
                            ("LEASING", "Leasing"),
                            ("SELLING", "Report for Sale"),
                            ("SOLD", "Sold"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("MANUAL", "Manual update"),
                            ("REORDER", "Batch reorder"),
                            ("CREATION", "Vehicle creation"),
                        ],
                        default="MANUAL",
                        max_length=10,
                    ),
                ),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vehicle_status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="vehicle.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["-changed_at"],
                "indexes": [
                    models.Index(
                        fields=["vehicle", "-changed_at"],
                        name="idx_status_hist_vehicle_date",
                    ),
                ],
            },
        ),
    ]
