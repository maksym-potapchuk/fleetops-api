from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0003_equipmentdefaultitem_created_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetservice",
            name="address",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
