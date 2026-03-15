from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0012_alter_partsexpensedetail_supplier_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspectionexpensedetail",
            name="registration_certificate",
            field=models.FileField(
                blank=True, null=True, upload_to="expenses/certificates/"
            ),
        ),
    ]
