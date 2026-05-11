from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0020_vehicledocument_doc_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="vehicle",
            name="tire_rim_diameter",
        ),
        migrations.AddField(
            model_name="vehicle",
            name="tire_size",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
