from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0012_vehicle_distance_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclephoto",
            name="is_cover",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterModelOptions(
            name="vehiclephoto",
            options={"ordering": ["-is_cover", "uploaded_at"]},
        ),
    ]
