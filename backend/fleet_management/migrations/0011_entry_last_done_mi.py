from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0010_regulation_mile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="last_done_mi",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Display-only mile value. Stored to avoid km↔mi rounding drift.",
                null=True,
            ),
        ),
    ]
