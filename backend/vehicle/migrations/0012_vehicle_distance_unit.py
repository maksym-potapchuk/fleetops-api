from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0011_add_company_client_amounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="distance_unit",
            field=models.CharField(
                choices=[("km", "Kilometers"), ("mi", "Miles")],
                default="km",
                max_length=2,
            ),
        ),
    ]
