from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0002_user_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="color",
            field=models.CharField(
                blank=True,
                help_text="Hex color for UI display, e.g. #E53E3E",
                max_length=7,
            ),
        ),
    ]
