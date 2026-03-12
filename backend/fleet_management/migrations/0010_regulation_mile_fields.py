from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0009_entry_next_due_km_override"),
    ]

    operations = [
        # Item-level (schema definition)
        migrations.AddField(
            model_name="fleetvehicleregulationitem",
            name="every_mi",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Display-only mile interval. Calculations always use every_km.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="fleetvehicleregulationitem",
            name="notify_before_mi",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Display-only mile threshold. Calculations always use notify_before_km.",
                null=True,
            ),
        ),
        # Entry-level (vehicle-specific override)
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="every_mi",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Vehicle-specific display-only mile interval override.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="notify_before_mi",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Vehicle-specific display-only mile threshold override.",
                null=True,
            ),
        ),
    ]
