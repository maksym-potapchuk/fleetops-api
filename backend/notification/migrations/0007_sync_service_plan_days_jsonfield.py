from django.db import migrations, models


class Migration(migrations.Migration):
    """State-only migration: tell Django the field is now JSONField.

    The actual column change was done in 0006 via RunSQL.
    """

    dependencies = [
        ("notification", "0006_service_plan_days_to_json"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="notificationpreferences",
                    name="service_plan_notify_days",
                    field=models.JSONField(
                        default=list,
                        help_text="Days before service plan to notify, e.g. [7, 3, 1]",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
