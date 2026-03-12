"""
Expense validation & edge-case tests.
======================================
Covers: required fields per category, category PROTECT, filters, invoice
file validation, cascade on vehicle delete.
"""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory

from .helpers import authenticate, make_user, make_vehicle


class ExpenseCategoryRequiredFieldsTest(TestCase):
    """Each system category enforces specific required fields via serializer validate()."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="val@example.com", username="valuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )
        self.washing_cat, _ = ExpenseCategory.objects.get_or_create(
            code="WASHING", defaults={"name": "Washing", "is_system": True, "order": 5}
        )
        self.fines_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FINES", defaults={"name": "Fines", "is_system": True, "order": 4}
        )
        self.inspection_cat, _ = ExpenseCategory.objects.get_or_create(
            code="INSPECTION",
            defaults={"name": "Inspection", "is_system": True, "order": 6},
        )

    def _base(self, category, **extra):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(category.id),
            "expense_date": "2026-03-01",
            "amount": "100.00",
        }
        payload.update(extra)
        return payload

    def test_fuel_without_fuel_types_returns_400(self):
        payload = self._base(self.fuel_cat)
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("fuel_types", response.data)

    def test_washing_without_wash_type_returns_400(self):
        payload = self._base(self.washing_cat)
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("wash_type", response.data)

    def test_fines_without_violation_type_returns_400(self):
        payload = self._base(self.fines_cat)
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("violation_type", response.data)

    def test_inspection_without_inspection_date_returns_400(self):
        payload = self._base(self.inspection_cat, official_cost="99.00")
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("inspection_date", response.data)

    def test_inspection_without_official_cost_returns_400(self):
        payload = self._base(self.inspection_cat, inspection_date="2026-03-01")
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("official_cost", response.data)


class ExpenseEdgeCasesTest(TestCase):
    """Category PROTECT, cascade on vehicle delete, invoice validation."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="val@example.com", username="valuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.other_cat, _ = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )

    def test_category_protect_prevents_delete(self):
        """Category with expenses cannot be deleted (PROTECT)."""
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("100.00"),
            expense_date=timezone.now(),
            created_by=self.user,
        )
        with self.assertRaises(ProtectedError):
            self.other_cat.delete()

    def test_vehicle_delete_cascades_expenses(self):
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("50.00"),
            expense_date=timezone.now(),
            created_by=self.user,
        )
        self.vehicle.delete()
        self.assertEqual(Expense.objects.count(), 0)

    def test_filter_by_date_range(self):
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("10.00"),
            expense_date=timezone.make_aware(timezone.datetime(2026, 1, 15)),
            created_by=self.user,
        )
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("20.00"),
            expense_date=timezone.make_aware(timezone.datetime(2026, 3, 15)),
            created_by=self.user,
        )
        response = self.client.get(
            f"{self.BASE_URL}?date_from=2026-03-01&date_to=2026-03-31"
        )
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount"], "20.00")

    def test_filter_by_amount_range(self):
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("50.00"),
            expense_date=timezone.make_aware(timezone.datetime(2026, 1, 1)),
            created_by=self.user,
        )
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("500.00"),
            expense_date=timezone.make_aware(timezone.datetime(2026, 1, 2)),
            created_by=self.user,
        )
        response = self.client.get(f"{self.BASE_URL}?min_amount=100&max_amount=600")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount"], "500.00")

    def test_invoice_jpg_rejected(self):
        """Invoice files only accept .pdf, .doc, .docx — not images."""
        jpg = SimpleUploadedFile(
            "photo.jpg", b"\xff\xd8\xff", content_type="image/jpeg"
        )
        response = self.client.post(
            self.BASE_URL,
            {
                "vehicle": str(self.vehicle.id),
                "category": str(self.other_cat.id),
                "amount": "100.00",
                "expense_date": "2026-03-01",
                "invoice_number": "TEST-JPG-001",
                "invoice_file": jpg,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invoice_file", response.data)
