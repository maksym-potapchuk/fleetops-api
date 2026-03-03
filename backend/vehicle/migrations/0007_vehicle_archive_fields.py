from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0006_technicalinspection"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="is_archived",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
