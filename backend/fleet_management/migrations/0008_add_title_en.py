from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0007_entry_vehicle_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetvehicleregulationschema",
            name="title_en",
            field=models.CharField(blank=True, max_length=155),
        ),
        migrations.AddField(
            model_name="fleetvehicleregulationitem",
            name="title_en",
            field=models.CharField(blank=True, max_length=155),
        ),
    ]
