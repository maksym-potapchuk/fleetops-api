"""
Quick expenses bulk submission tests.
======================================
Simulates the quick-expense wizard submitting multiple entries at once,
each containing up to 15 line items (parts, service_items, fuel sub-entries).
Focuses on reproducing a bug where valid amounts are rejected as "too long".
"""

from decimal import Decimal
import json

from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory, ExpensePart, ServiceItem
from fleet_management.models import FleetService

from .helpers import authenticate, make_user, make_vehicle


class QuickExpenseBulkPartsTest(TestCase):
    """POST /vehicle/{pk}/expenses/ — PARTS category with 15 items."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="qbulk@example.com", username="qbulkuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.parts_cat, _ = ExpenseCategory.objects.get_or_create(
            code="PARTS", defaults={"name": "Parts", "is_system": True, "order": 3}
        )
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def _parts_payload(self, parts, **extra):
        payload = {
            "category": str(self.parts_cat.id),
            "expense_date": "2026-03-20",
            "amount": "0",
            "parts_json": json.dumps(parts),
        }
        payload.update(extra)
        return payload

    def test_15_cheap_parts_accepted(self):
        """15 parts with small unit_price (sum well within max_digits=10)."""
        parts = [
            {"name": f"Part {i}", "quantity": 1, "unit_price": "50.00"}
            for i in range(15)
        ]
        response = self.client.post(
            self.url, self._parts_payload(parts), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "750.00")
        self.assertEqual(
            ExpensePart.objects.filter(expense_id=response.data["id"]).count(), 15
        )

    def test_15_medium_parts_accepted(self):
        """15 parts with moderate unit_price — total 15000.00."""
        parts = [
            {"name": f"Part {i}", "quantity": 1, "unit_price": "1000.00"}
            for i in range(15)
        ]
        response = self.client.post(
            self.url, self._parts_payload(parts), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "15000.00")

    def test_15_parts_with_quantity_accepted(self):
        """15 parts with quantity > 1 — total = sum(qty * price)."""
        parts = [
            {"name": f"Part {i}", "quantity": 3, "unit_price": "250.50"}
            for i in range(15)
        ]
        expected = Decimal("250.50") * 3 * 15  # 11272.50
        response = self.client.post(
            self.url, self._parts_payload(parts), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["amount"]), expected)

    def test_15_parts_with_decimal_prices_accepted(self):
        """15 parts with prices like 99.99, 149.50 — mixed decimals."""
        prices = [
            "99.99",
            "149.50",
            "75.25",
            "200.00",
            "45.00",
            "120.75",
            "88.50",
            "33.33",
            "67.89",
            "150.00",
            "225.50",
            "10.99",
            "89.95",
            "55.55",
            "300.00",
        ]
        parts = [
            {"name": f"Part {i}", "quantity": 1, "unit_price": prices[i]}
            for i in range(15)
        ]
        expected = sum(Decimal(p) for p in prices)
        response = self.client.post(
            self.url, self._parts_payload(parts), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["amount"]), expected)


class QuickExpenseBulkServiceTest(TestCase):
    """POST /vehicle/{pk}/expenses/ — SERVICE category with 15 items."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="qsvc@example.com", username="qsvcuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.service_cat, _ = ExpenseCategory.objects.get_or_create(
            code="SERVICE", defaults={"name": "Service", "is_system": True, "order": 2}
        )
        self.fleet_svc = FleetService.objects.create(name="Test Garage")
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def _service_payload(self, items, **extra):
        payload = {
            "category": str(self.service_cat.id),
            "expense_date": "2026-03-20",
            "amount": "0",
            "service": str(self.fleet_svc.pk),
            "service_items_json": json.dumps(items),
        }
        payload.update(extra)
        return payload

    def test_15_service_items_accepted(self):
        """15 service items with small prices (sum well within max_digits=10)."""
        items = [{"name": f"Service {i}", "price": "100.00"} for i in range(15)]
        response = self.client.post(
            self.url, self._service_payload(items), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "1500.00")
        self.assertEqual(
            ServiceItem.objects.filter(expense_id=response.data["id"]).count(), 15
        )

    def test_15_service_items_mixed_prices_accepted(self):
        """15 service items with varied prices."""
        prices = [
            "50.00",
            "120.00",
            "75.50",
            "200.00",
            "30.00",
            "180.00",
            "95.00",
            "60.50",
            "140.00",
            "110.00",
            "45.00",
            "250.00",
            "85.00",
            "170.00",
            "65.00",
        ]
        items = [{"name": f"Service {i}", "price": prices[i]} for i in range(15)]
        expected = sum(Decimal(p) for p in prices)
        response = self.client.post(
            self.url, self._service_payload(items), format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["amount"]), expected)


class QuickExpenseBulkFuelTest(TestCase):
    """POST /vehicle/{pk}/expenses/ — FUEL with 15 sub-entries (each separate request)."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="qfuel@example.com", username="qfueluser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def test_15_fuel_entries_all_created(self):
        """Simulate quick expense wizard: 15 fuel sub-entries → 15 separate API calls."""
        amounts = [
            "80.00",
            "95.50",
            "110.00",
            "65.00",
            "120.25",
            "85.00",
            "90.00",
            "105.50",
            "70.00",
            "115.00",
            "88.00",
            "92.50",
            "100.00",
            "78.00",
            "130.00",
        ]
        created_ids = []
        for i, amount in enumerate(amounts):
            response = self.client.post(
                self.url,
                {
                    "category": str(self.fuel_cat.id),
                    "expense_date": "2026-03-20",
                    "amount": amount,
                    "fuel_types": json.dumps(["DIESEL"]),
                },
                format="multipart",
            )
            self.assertEqual(
                response.status_code,
                201,
                f"Fuel entry {i} failed: {response.data}",
            )
            created_ids.append(response.data["id"])

        self.assertEqual(len(created_ids), 15)
        total = Expense.objects.filter(
            vehicle=self.vehicle, category=self.fuel_cat
        ).count()
        self.assertEqual(total, 15)


class QuickExpenseAllCategoriesTest(TestCase):
    """Simulate adding one entry per category (15 total) in a single quick-expense session."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="qall@example.com", username="qalluser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

        self.cats = {}
        category_defs = [
            ("FUEL", "Fuel", 1),
            ("SERVICE", "Service", 2),
            ("PARTS", "Parts", 3),
            ("FINES", "Fines", 4),
            ("WASHING", "Washing", 5),
            ("INSPECTION", "Inspection", 6),
            ("OTHER", "Other", 7),
            ("PARKING", "Parking", 8),
            ("ACCESSORIES", "Accessories", 9),
            ("DOCUMENTS", "Documents", 10),
        ]
        for code, name, order in category_defs:
            cat, _ = ExpenseCategory.objects.get_or_create(
                code=code, defaults={"name": name, "is_system": True, "order": order}
            )
            self.cats[code] = cat
        self.fleet_svc = FleetService.objects.create(name="Bulk Garage")

    def _build_payloads(self):
        """Build 15 payloads — one per category type with category-specific fields."""
        payloads = []

        # 1-2: FUEL entries
        for i in range(2):
            payloads.append(
                {
                    "category": str(self.cats["FUEL"].id),
                    "expense_date": "2026-03-20",
                    "amount": f"{80 + i * 10}.00",
                    "fuel_types": json.dumps(["DIESEL"]),
                }
            )

        # 3: SERVICE with 15 items
        service_items = [{"name": f"Job {j}", "price": "50.00"} for j in range(15)]
        payloads.append(
            {
                "category": str(self.cats["SERVICE"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "service": str(self.fleet_svc.pk),
                "service_items_json": json.dumps(service_items),
            }
        )

        # 4: PARTS with 15 items
        parts = [
            {"name": f"Bolt {j}", "quantity": 2, "unit_price": "10.00"}
            for j in range(15)
        ]
        payloads.append(
            {
                "category": str(self.cats["PARTS"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "parts_json": json.dumps(parts),
            }
        )

        # 5: ACCESSORIES with 15 items
        acc_parts = [
            {"name": f"Acc {j}", "quantity": 1, "unit_price": "25.00"}
            for j in range(15)
        ]
        payloads.append(
            {
                "category": str(self.cats["ACCESSORIES"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "parts_json": json.dumps(acc_parts),
            }
        )

        # 6: DOCUMENTS with 15 items
        doc_parts = [
            {"name": f"Doc {j}", "quantity": 1, "unit_price": "15.00"}
            for j in range(15)
        ]
        payloads.append(
            {
                "category": str(self.cats["DOCUMENTS"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "parts_json": json.dumps(doc_parts),
            }
        )

        # 7: WASHING
        payloads.append(
            {
                "category": str(self.cats["WASHING"].id),
                "expense_date": "2026-03-20",
                "amount": "45.00",
                "wash_type": "FULL",
            }
        )

        # 8: FINES
        payloads.append(
            {
                "category": str(self.cats["FINES"].id),
                "expense_date": "2026-03-20",
                "amount": "500.00",
                "violation_type": "Speeding",
                "fine_number": "FN-BULK-001",
            }
        )

        # 9: INSPECTION
        payloads.append(
            {
                "category": str(self.cats["INSPECTION"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "inspection_date": "2026-03-20",
                "official_cost": "99.00",
                "additional_cost": "50.00",
            }
        )

        # 10: OTHER
        payloads.append(
            {
                "category": str(self.cats["OTHER"].id),
                "expense_date": "2026-03-20",
                "amount": "200.00",
                "expense_for": "Miscellaneous",
            }
        )

        # 11: PARKING
        payloads.append(
            {
                "category": str(self.cats["PARKING"].id),
                "expense_date": "2026-03-20",
                "amount": "30.00",
            }
        )

        # 12-15: More FUEL and OTHER to reach 15 total
        for i in range(4):
            payloads.append(
                {
                    "category": str(self.cats["OTHER"].id),
                    "expense_date": "2026-03-20",
                    "amount": f"{50 + i * 25}.00",
                }
            )

        return payloads

    def test_15_mixed_entries_all_created(self):
        """Submit 15 entries across all categories — simulates full quick expense session."""
        payloads = self._build_payloads()
        self.assertEqual(len(payloads), 15)

        for i, payload in enumerate(payloads):
            response = self.client.post(self.url, payload, format="multipart")
            self.assertEqual(
                response.status_code,
                201,
                f"Entry {i} failed ({payload.get('category')}): {response.data}",
            )

        total = Expense.objects.filter(vehicle=self.vehicle).count()
        self.assertEqual(total, 15)

    def test_parts_15_items_amount_equals_computed(self):
        """PARTS with 15 items: amount field matches sum(qty * unit_price)."""
        parts = [
            {"name": f"Part {i}", "quantity": 2, "unit_price": "10.00"}
            for i in range(15)
        ]
        response = self.client.post(
            self.url,
            {
                "category": str(self.cats["PARTS"].id),
                "expense_date": "2026-03-20",
                "amount": "0",
                "parts_json": json.dumps(parts),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        # 15 * 2 * 10.00 = 300.00
        self.assertEqual(response.data["amount"], "300.00")
