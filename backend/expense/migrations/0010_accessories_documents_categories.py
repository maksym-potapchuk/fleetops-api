from django.db import migrations


def create_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.create(
        code="ACCESSORIES",
        name="Аксесуари",
        icon="shopping-bag",
        color="#EC4899",
        is_system=True,
        order=8,
    )
    ExpenseCategory.objects.create(
        code="DOCUMENTS",
        name="Документи",
        icon="file-text",
        color="#6366F1",
        is_system=True,
        order=9,
    )


def remove_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model("expense", "ExpenseCategory")
    ExpenseCategory.objects.filter(code__in=["ACCESSORIES", "DOCUMENTS"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0009_inspectionexpensedetail_linked_inspection_and_more"),
    ]

    operations = [
        migrations.RunPython(create_categories, remove_categories),
    ]
