from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("driver", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="driver",
            name="telegram_id",
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
    ]

