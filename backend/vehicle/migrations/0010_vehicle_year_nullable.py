from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0009_add_updated_at_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="year",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
