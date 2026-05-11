from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0018_vehicledocument"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="tire_rim_diameter",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
