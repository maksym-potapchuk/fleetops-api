from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet_management", "0008_add_title_en"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetvehicleregulationentry",
            name="next_due_km_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="One-time override for next_due_km. Cleared on next mark-done.",
                null=True,
            ),
        ),
    ]
