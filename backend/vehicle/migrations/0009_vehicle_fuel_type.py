from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicle", "0008_mileagelog"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="fuel_type",
            field=models.CharField(
                choices=[
                    ("GASOLINE", "Gasoline"),
                    ("DIESEL", "Diesel"),
                    ("LPG", "LPG"),
                    ("LPG_GASOLINE", "LPG + Gasoline"),
                    ("ELECTRIC", "Electric"),
                    ("HYBRID", "Hybrid"),
                ],
                default="GASOLINE",
                max_length=20,
            ),
        ),
    ]
