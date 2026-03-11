from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicle", "0007_car_number_optional_temporary_plate"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(
                fields=["status", "status_position"],
                name="idx_vehicle_status_pos",
            ),
        ),
    ]
