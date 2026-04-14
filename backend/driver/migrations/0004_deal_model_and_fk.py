from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("driver", "0003_drivervehicledeal_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Deal",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("status", models.CharField(max_length=50)),
            ],
            options={
                "db_table": "deal",
                "managed": False,
            },
        ),
        migrations.RemoveField(
            model_name="drivervehicledeal",
            name="status",
        ),
        migrations.RemoveField(
            model_name="drivervehicledeal",
            name="deal_id",
        ),
        migrations.AddField(
            model_name="drivervehicledeal",
            name="deal",
            field=models.ForeignKey(
                db_column="deal_id",
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="vehicle_deals",
                to="driver.deal",
            ),
        ),
    ]
