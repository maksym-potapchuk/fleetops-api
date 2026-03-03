from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0004_vehicleownerhistory_vehiclephoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="color",
            field=models.CharField(default="", max_length=30),
            preserve_default=False,
        ),
    ]
