"""
Vehicle-scoped expense API tests — POST /vehicle/{pk}/expenses/.

Verifies that expenses can be created via the vehicle-scoped endpoint
where vehicle ID comes from the URL (not the request body).
"""

import json
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from fleet_management.models import FleetService
from vehicle.models import ManufacturerChoices, Vehicle, VehicleStatus

from .models import Expense, ExpenseCategory, ExpensePart, ServiceItem


def make_user(email="vexp@example.com", password="pass123!", username="vexpuser"):
    return User.objects.create_user(email=email, password=password, username=username)


def make_vehicle(**kwargs):
    defaults = {
        "model": "Camry",
        "manufacturer": ManufacturerChoices.TOYOTA,
        "year": 2022,
        "cost": "25000.00",
        "vin_number": "1HGBH41JXMN109186",
        "car_number": "AA6601BB",
        "initial_km": 0,
        "status": VehicleStatus.PREPARATION,
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)


class VehicleExpenseCreateTest(TestCase):
    """POST /vehicle/{pk}/expenses/ — vehicle from URL, not body."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )
        self.service_cat, _ = ExpenseCategory.objects.get_or_create(
            code="SERVICE", defaults={"name": "Service", "is_system": True, "order": 2}
        )
        self.washing_cat, _ = ExpenseCategory.objects.get_or_create(
            code="WASHING", defaults={"name": "Washing", "is_system": True, "order": 5}
        )
        self.inspection_cat, _ = ExpenseCategory.objects.get_or_create(
            code="INSPECTION", defaults={"name": "Inspection", "is_system": True, "order": 6}
        )
        self.fines_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FINES", defaults={"name": "Fines", "is_system": True, "order": 4}
        )
        self.other_cat, _ = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/expenses/"

    def test_create_fuel_without_vehicle_in_body_returns_201(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.fuel_cat.id),
                "expense_date": "2026-03-01",
                "amount": "100.00",
                "liters": "40.00",
                "fuel_type": "DIESEL",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        expense = Expense.objects.get(id=response.data["id"])
        self.assertEqual(expense.vehicle_id, self.vehicle.id)
        self.assertEqual(response.data["category_code"], "FUEL")

    def test_create_washing_returns_201(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.washing_cat.id),
                "expense_date": "2026-03-01",
                "amount": "50.00",
                "wash_type": "FULL",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["wash_type"], "FULL")

    def test_create_fines_returns_201(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.fines_cat.id),
                "expense_date": "2026-03-01",
                "amount": "500.00",
                "violation_type": "Speeding",
                "fine_number": "FN-001",
                "fine_date": "2026-02-28",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["violation_type"], "Speeding")
        self.assertEqual(response.data["fine_number"], "FN-001")

    def test_create_inspection_auto_computes_amount(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.inspection_cat.id),
                "expense_date": "2026-03-01",
                "amount": "0",
                "inspection_date": "2026-03-01",
                "official_cost": "99.00",
                "additional_cost": "50.00",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], "149.00")

    def test_create_service_with_items_returns_201(self):
        fleet_svc = FleetService.objects.create(name="QuickFix Garage")
        items = [{"name": "Brake fluid flush", "price": "80.00"}]
        response = self.client.post(
            self.url,
            {
                "category": str(self.service_cat.id),
                "expense_date": "2026-03-01",
                "amount": "0",
                "service": str(fleet_svc.pk),
                "service_items_json": json.dumps(items),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], "80.00")
        self.assertEqual(ServiceItem.objects.count(), 1)

    def test_create_other_returns_201(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.other_cat.id),
                "expense_date": "2026-03-01",
                "amount": "1000.00",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], "1000.00")

    def test_list_returns_only_vehicle_expenses(self):
        other_vehicle = make_vehicle(car_number="BB7777CC", vin_number="2HGBH41JXMN109186")
        Expense.objects.create(
            vehicle=self.vehicle, category=self.other_cat,
            amount=Decimal("100"), expense_date="2026-01-01", created_by=self.user,
        )
        Expense.objects.create(
            vehicle=other_vehicle, category=self.other_cat,
            amount=Decimal("200"), expense_date="2026-01-01", created_by=self.user,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount"], "100.00")

    def test_missing_required_field_returns_400(self):
        response = self.client.post(
            self.url,
            {
                "category": str(self.fuel_cat.id),
                "expense_date": "2026-03-01",
                "amount": "100.00",
                # missing liters and fuel_type
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("liters", response.data)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, 401)
