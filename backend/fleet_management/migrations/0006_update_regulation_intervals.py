from django.db import migrations


class Migration(migrations.Migration):
    """Seed data moved to management command: create_vehicle_reg_basic_schema."""

    dependencies = [
        ("fleet_management", "0005_remove_tech_inspection_item"),
    ]

    operations = []
