from django.db import migrations, models


def convert_int_to_list(apps, schema_editor):
    """Convert existing integer value to a JSON list, e.g. 4 → [4]."""
    NotificationPreferences = apps.get_model("notification", "NotificationPreferences")
    for pref in NotificationPreferences.objects.all():
        val = pref.service_plan_notify_days
        if isinstance(val, int):
            pref.service_plan_notify_days = [val] if val else [3, 1]
            pref.save(update_fields=["service_plan_notify_days"])


class Migration(migrations.Migration):
    dependencies = [
        ("notification", "0005_add_regulation_notify_before_km"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationpreferences",
            name="service_plan_notify_days",
            field=models.JSONField(
                default=list,
                help_text="Days before service plan to notify, e.g. [7, 3, 1]",
            ),
        ),
        migrations.RunPython(convert_int_to_list, migrations.RunPython.noop),
    ]
