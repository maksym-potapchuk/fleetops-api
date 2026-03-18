from django.db import migrations


def populate_edited_by(apps, schema_editor):
    """Set edited_by = created_by for all existing expenses where edited_by is NULL."""
    from django.db.models import F

    Expense = apps.get_model("expense", "Expense")
    updated = Expense.objects.filter(
        edited_by__isnull=True, created_by__isnull=False
    ).update(edited_by=F("created_by"))
    if updated:
        print(f"\n  -> Populated edited_by for {updated} expense(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("expense", "0014_add_edited_by"),
    ]

    operations = [
        migrations.RunPython(populate_edited_by, migrations.RunPython.noop),
    ]
