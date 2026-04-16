"""
Quick expenses stress test — all category types via vehicle expense endpoint,
CLIENT/COMPANY payer, 1000 expenses to 1 vehicle, edge-case amounts/dates.
"""

import time
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory, FuelExpenseDetail, ServiceExpenseDetail
from expense.tests.helpers import authenticate, make_user, make_vehicle
from fleet_management.models import FleetService


class AllCategoryTypesTest(TestCase):
    """POST /api/v1/vehicle/{id}/expenses/ — every category code."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        # Ensure all categories exist
        self.cats = {}
        for code, name, order in [
            ("FUEL", "Fuel", 1), ("SERVICE", "Service", 2),
            ("WASHING", "Washing", 3), ("FINES", "Fines", 4),
            ("PARKING", "Parking", 5), ("INSPECTION", "Inspection", 6),
            ("OTHER", "Other", 7), ("PARTS", "Parts", 8),
            ("ACCESSORIES", "Accessories", 9), ("DOCUMENTS", "Documents", 10),
        ]:
            cat, _ = ExpenseCategory.objects.get_or_create(
                code=code, defaults={"name": name, "is_system": True, "order": order}
            )
            self.cats[code] = cat
        self.fleet_service = FleetService.objects.create(name="TestService")

    def _url(self):
        return f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def _post(self, data):
        return self.client.post(self._url(), data, format="multipart")

    def test_fuel_with_fuel_types(self):
        res = self._post({
            "category": str(self.cats["FUEL"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "100.00",
            "fuel_types": '["DIESEL","LPG"]',
        })
        self.assertEqual(res.status_code, 201)
        detail = FuelExpenseDetail.objects.first()
        self.assertEqual(detail.fuel_types, ["DIESEL", "LPG"])

    def test_service_with_items(self):
        res = self._post({
            "category": str(self.cats["SERVICE"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "service": str(self.fleet_service.id),
            "service_items_json": '[{"name":"Oil change","price":"200.00"},{"name":"Filter","price":"50.00"}]',
        })
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertEqual(expense.amount, Decimal("250.00"))

    def test_washing_with_wash_type(self):
        res = self._post({
            "category": str(self.cats["WASHING"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "30.00",
            "wash_type": "FULL",
        })
        self.assertEqual(res.status_code, 201)

    def test_fines_with_violation(self):
        res = self._post({
            "category": str(self.cats["FINES"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "500.00",
            "violation_type": "Speeding",
            "fine_number": "FN-001",
            "fine_date": "2026-03-10",
        })
        self.assertEqual(res.status_code, 201)

    def test_parking_simple(self):
        res = self._post({
            "category": str(self.cats["PARKING"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "15.00",
        })
        self.assertEqual(res.status_code, 201)

    def test_inspection_with_costs(self):
        res = self._post({
            "category": str(self.cats["INSPECTION"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "inspection_date": "2026-03-15",
            "official_cost": "150.00",
            "additional_cost": "50.00",
        })
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertEqual(expense.amount, Decimal("200.00"))

    def test_other_with_description(self):
        res = self._post({
            "category": str(self.cats["OTHER"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "75.00",
            "expense_for": "Мийка двигуна",
        })
        self.assertEqual(res.status_code, 201)

    def test_parts_with_items(self):
        res = self._post({
            "category": str(self.cats["PARTS"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "source_name": "Allegro",
            "supplier_type": "SHOP",
            "parts_json": '[{"name":"Brake pads","quantity":2,"unit_price":"120.00"}]',
        })
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertEqual(expense.amount, Decimal("240.00"))

    def test_accessories_with_parts(self):
        res = self._post({
            "category": str(self.cats["ACCESSORIES"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "parts_json": '[{"name":"Floor mats","quantity":1,"unit_price":"80.00"}]',
        })
        self.assertEqual(res.status_code, 201)

    def test_documents_with_parts(self):
        res = self._post({
            "category": str(self.cats["DOCUMENTS"].id),
            "expense_date": "2026-03-15T12:00:00Z",
            "parts_json": '[{"name":"Registration fee","quantity":1,"unit_price":"500.00"}]',
        })
        self.assertEqual(res.status_code, 201)


class ClientPayerQuickExpenseTest(TestCase):
    """POST with payer_type=CLIENT — split amounts, approval status."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="client@test.com", username="clientuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(vin_number="CLIENTVIN0000001", car_number="CL0001XX")
        self.cat = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )[0]

    def _url(self):
        return f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def test_client_payer_creates_draft_status(self):
        res = self.client.post(self._url(), {
            "category": str(self.cat.id),
            "expense_date": "2026-03-15T12:00:00Z",
            "payer_type": "CLIENT",
            "company_amount": "50.00",
            "client_amount": "100.00",
        }, format="multipart")
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertEqual(expense.approval_status, "DRAFT")
        self.assertEqual(expense.amount, Decimal("150.00"))

    def test_client_payer_without_amounts_fails(self):
        res = self.client.post(self._url(), {
            "category": str(self.cat.id),
            "expense_date": "2026-03-15T12:00:00Z",
            "payer_type": "CLIENT",
        }, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_company_payer_has_no_approval_status(self):
        res = self.client.post(self._url(), {
            "category": str(self.cat.id),
            "expense_date": "2026-03-15T12:00:00Z",
            "amount": "100.00",
            "payer_type": "COMPANY",
        }, format="multipart")
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertIsNone(expense.approval_status)

    def test_client_zero_company_full_client(self):
        res = self.client.post(self._url(), {
            "category": str(self.cat.id),
            "expense_date": "2026-03-15T12:00:00Z",
            "payer_type": "CLIENT",
            "company_amount": "0.00",
            "client_amount": "200.00",
        }, format="multipart")
        self.assertEqual(res.status_code, 201)
        expense = Expense.objects.first()
        self.assertEqual(expense.amount, Decimal("200.00"))


class BulkQuickExpenseTest(TestCase):
    """Create 1000 expenses for 1 vehicle via API — perf + data integrity."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="bulk@quick.com", username="bulkquick")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(vin_number="BULKVIN00000001", car_number="BQ0001XX")
        self.cat = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )[0]
        self.fuel_cat = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )[0]

    def _url(self):
        return f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def test_create_1000_expenses_via_api(self):
        """Sequential creation of 1000 expenses — check count and time."""
        t0 = time.time()
        success = 0
        fail = 0
        for i in range(1000):
            res = self.client.post(self._url(), {
                "category": str(self.cat.id),
                "expense_date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T12:00:00Z",
                "amount": f"{10 + i * 0.5:.2f}",
            }, format="multipart")
            if res.status_code == 201:
                success += 1
            else:
                fail += 1
        elapsed = time.time() - t0

        self.assertEqual(Expense.objects.filter(vehicle=self.vehicle).count(), success)
        self.assertEqual(fail, 0, f"{fail} expenses failed to create")
        self.assertLess(elapsed, 120, f"1000 API calls took {elapsed:.1f}s")

    def test_list_1000_expenses_response(self):
        """Bulk create via ORM, then list via API."""
        Expense.objects.bulk_create([
            Expense(
                vehicle=self.vehicle, category=self.cat,
                expense_date=f"2026-01-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal(str(10 + i)), payer_type="COMPANY",
                created_by=self.user,
            )
            for i in range(1000)
        ])
        t0 = time.time()
        res = self.client.get(self._url())
        elapsed = time.time() - t0
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1000)
        self.assertLess(elapsed, 5, f"List took {elapsed:.1f}s")

    def test_summary_with_1000_expenses(self):
        """Check summary aggregation with 1000 expenses."""
        expenses = []
        for i in range(500):
            expenses.append(Expense(
                vehicle=self.vehicle, category=self.cat,
                expense_date=f"2026-01-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal("100.00"), payer_type="COMPANY",
                created_by=self.user,
            ))
        for i in range(500):
            expenses.append(Expense(
                vehicle=self.vehicle, category=self.fuel_cat,
                expense_date=f"2026-02-{(i % 28) + 1:02d}T12:00:00Z",
                amount=Decimal("50.00"), payer_type="COMPANY",
                created_by=self.user,
            ))
        Expense.objects.bulk_create(expenses)

        res = self.client.get(f"/api/v1/vehicle/{self.vehicle.id}/expenses/summary/")
        self.assertEqual(res.status_code, 200)
        # 500*100 + 500*50 = 75000
        total = sum(float(c["total"]) for c in res.data["categories"])
        self.assertAlmostEqual(total, 75000.0, places=2)
