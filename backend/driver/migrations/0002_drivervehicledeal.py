from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("driver", "0001_initial"),
        ("vehicle", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverVehicleDeal",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                (
                    "deal_id",
                    models.UUIDField(),
                ),
                (
                    "driver",
                    models.ForeignKey(
                        db_column="driver_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="deals",
                        to="driver.driver",
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        blank=True,
                        db_column="vehicle_id",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="deals",
                        to="vehicle.vehicle",
                    ),
                ),
            ],
            options={
                "db_table": "driver_vehicle_deal",
                "managed": False,
            },
        ),
    ]
