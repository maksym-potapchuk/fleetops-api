from django.core.management.base import BaseCommand

from config import cache_utils
from expense.models import ExpenseCategory

DEFAULTS = [
    {"code": "FUEL", "name": "Пальне", "icon": "fuel", "color": "#F59E0B", "order": 1},
    {"code": "SERVICE", "name": "Сервіс", "icon": "wrench", "color": "#3B82F6", "order": 2},
    {"code": "PARTS", "name": "Запчастини", "icon": "package", "color": "#8B5CF6", "order": 3},
    {
        "code": "INSURANCE",
        "name": "Страховка",
        "icon": "shield",
        "color": "#10B981",
        "is_active": False,
        "order": 4,
    },
    {"code": "WASHING", "name": "Хімчистка", "icon": "droplets", "color": "#06B6D4", "order": 5},
    {"code": "INSPECTION", "name": "Technical Inspection", "icon": "", "color": "", "order": 6},
    {"code": "FINES", "name": "Штрафи", "icon": "alert-triangle", "color": "#EF4444", "order": 7},
    {"code": "OTHER", "name": "Інше", "icon": "more-horizontal", "color": "#64748B", "order": 8},
    {"code": "ACCESSORIES", "name": "Аксесуари", "icon": "shopping-bag", "color": "#EC4899", "order": 9},
    {"code": "DOCUMENTS", "name": "Документи", "icon": "file-text", "color": "#6366F1", "order": 10},
]


class Command(BaseCommand):
    help = "Seed default expense categories (idempotent)"

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for item in DEFAULTS:
            code = item["code"]
            defaults = {k: v for k, v in item.items() if k != "code"}
            defaults["is_system"] = True

            _, was_created = ExpenseCategory.objects.update_or_create(
                code=code, defaults=defaults
            )
            if was_created:
                created += 1
            else:
                updated += 1

        cache_utils.invalidate_categories()

        active = ExpenseCategory.objects.filter(is_active=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} created, {updated} updated. Active categories: {active}"
            )
        )
