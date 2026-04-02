from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("driver", "0002_drivervehicledeal"),
    ]

    operations = [
        migrations.AddField(
            model_name="drivervehicledeal",
            name="status",
            field=models.CharField(max_length=50),
        ),
    ]
