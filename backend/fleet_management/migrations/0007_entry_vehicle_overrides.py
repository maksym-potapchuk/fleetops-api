from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0006_update_regulation_intervals"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="every_km",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Vehicle-specific override. Falls back to item.every_km when null.",
            ),
        ),
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="notify_before_km",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Vehicle-specific override. Falls back to item.notify_before_km when null.",
            ),
        ),
    ]
