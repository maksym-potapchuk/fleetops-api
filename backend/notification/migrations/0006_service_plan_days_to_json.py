from django.db import connection, migrations, models


def forwards(apps, schema_editor):
    """Convert service_plan_notify_days from integer to JSON array."""
    if connection.vendor == "sqlite":
        # SQLite: AlterField handles this natively (no type constraints)
        return

    # PostgreSQL: manual type conversion needed
    with schema_editor.connection.cursor() as cursor:
        # Drop check constraint
        cursor.execute("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    WHERE rel.relname = 'notification_notificationpreferences'
                      AND con.contype = 'c'
                      AND pg_get_constraintdef(con.oid) LIKE '%%service_plan_notify_days%%'
                LOOP
                    EXECUTE 'ALTER TABLE notification_notificationpreferences DROP CONSTRAINT ' || r.conname;
                END LOOP;
            END $$;
        """)
        # Convert integer → jsonb
        cursor.execute("""
            ALTER TABLE notification_notificationpreferences
            ALTER COLUMN service_plan_notify_days
            TYPE jsonb USING to_jsonb(ARRAY[service_plan_notify_days]);
        """)
        # Set default
        cursor.execute("""
            ALTER TABLE notification_notificationpreferences
            ALTER COLUMN service_plan_notify_days SET DEFAULT '[]'::jsonb;
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("notification", "0005_add_regulation_notify_before_km"),
    ]

    operations = [
        # For SQLite (tests): standard AlterField works
        migrations.AlterField(
            model_name="notificationpreferences",
            name="service_plan_notify_days",
            field=models.JSONField(
                default=list,
                help_text="Days before service plan to notify, e.g. [7, 3, 1]",
            ),
        ),
        # For PostgreSQL (prod): RunPython handles the actual type conversion
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
