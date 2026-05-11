from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0019_vehicle_tire_rim_diameter"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicledocument",
            name="doc_type",
            field=models.CharField(
                choices=[("TDT", "TDT"), ("OTHER", "Other")],
                default="OTHER",
                max_length=10,
            ),
        ),
    ]
