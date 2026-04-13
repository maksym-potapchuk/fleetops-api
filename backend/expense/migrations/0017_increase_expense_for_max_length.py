from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0016_expense_exclude_from_cost"),
    ]

    operations = [
        migrations.AlterField(
            model_name="expense",
            name="expense_for",
            field=models.CharField(max_length=500, blank=True),
        ),
        migrations.AlterField(
            model_name="serviceitem",
            name="name",
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name="expensepart",
            name="name",
            field=models.CharField(max_length=500),
        ),
    ]
