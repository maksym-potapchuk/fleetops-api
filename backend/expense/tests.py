"""
Expense API Tests — Hybrid architecture with dynamic categories.
"""

from decimal import Decimal
import json

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from fleet_management.models import FleetService
from vehicle.models import ManufacturerChoices, TechnicalInspection, Vehicle, VehicleStatus

from .models import Expense, ExpenseCategory, ExpensePart, ServiceItem


def make_user(email="expense@example.com", password="pass123!", username="expuser"):
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


class ExpenseAPITest(TestCase):
    BASE_URL = "/api/v1/expense/"

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
        self.other_cat, _ = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )
        self.parts_cat, _ = ExpenseCategory.objects.get_or_create(
            code="PARTS", defaults={"name": "Parts", "is_system": True, "order": 3}
        )
        self.custom_cat = ExpenseCategory.objects.create(
            code=None, name="Toll Roads", is_system=False, order=10
        )
        self.washing_cat, _ = ExpenseCategory.objects.get_or_create(
            code="WASHING", defaults={"name": "Washing", "is_system": True, "order": 5}
        )
        self.inspection_cat, _ = ExpenseCategory.objects.get_or_create(
            code="INSPECTION", defaults={"name": "Inspection", "is_system": True, "order": 6}
        )

    def _fuel_payload(self, **overrides):
        base = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.fuel_cat.id),
            "amount": "150.00",
            "expense_date": "2026-02-15",
            "liters": "45.00",
            "fuel_type": "GASOLINE",
        }
        base.update(overrides)
        return base

    def test_create_fuel_expense_returns_201(self):
        response = self.client.post(
            self.BASE_URL, self._fuel_payload(), format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["category_code"], "FUEL")
        self.assertEqual(response.data["amount"], "150.00")
        self.assertEqual(Expense.objects.count(), 1)
        expense = Expense.objects.first()
        self.assertTrue(hasattr(expense, "fuel_detail"))

    def test_create_fuel_without_liters_returns_400(self):
        payload = self._fuel_payload()
        del payload["liters"]
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("liters", response.data)

    def test_create_service_with_fleet_service_and_items(self):
        fleet_svc = FleetService.objects.create(name="AutoService Plus")
        items = [
            {"name": "Oil change", "price": "120.00"},
            {"name": "Filter replacement", "price": "80.00"},
        ]
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.service_cat.id),
            "expense_date": "2026-02-20",
            "service": str(fleet_svc.pk),
            "service_items_json": json.dumps(items),
        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["service"], fleet_svc.pk)
        self.assertEqual(response.data["service_name"], "AutoService Plus")
        self.assertEqual(response.data["amount"], "200.00")
        self.assertEqual(ServiceItem.objects.count(), 2)
        self.assertEqual(len(response.data["service_items"]), 2)

    def test_create_parts_expense_auto_computes_amount(self):
        parts = [
            {"name": "Oil filter", "quantity": 1, "unit_price": "25.00"},
            {"name": "Brake pads", "quantity": 2, "unit_price": "80.00"},
        ]
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.parts_cat.id),
            "expense_date": "2026-02-20",
            "parts_json": json.dumps(parts),
        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ExpensePart.objects.count(), 2)
        # 25*1 + 80*2 = 185
        self.assertEqual(response.data["amount"], "185.00")
        self.assertEqual(response.data["parts"][0]["name"], "Brake pads")

    def test_create_inspection_auto_computes_amount(self):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.inspection_cat.id),
            "expense_date": "2026-03-01",
            "inspection_date": "2026-03-01",
            "official_cost": "99.00",
            "additional_cost": "50.00",
        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["category_code"], "INSPECTION")
        # 99 + 50 = 149
        self.assertEqual(response.data["amount"], "149.00")
        self.assertEqual(str(response.data["inspection_date"]), "2026-03-01")
        self.assertEqual(str(response.data["official_cost"]), "99.00")
        self.assertEqual(str(response.data["additional_cost"]), "50.00")

    def test_create_custom_category_expense(self):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.custom_cat.id),
            "amount": "50.00",
            "expense_date": "2026-03-01",

        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["category_code"])
        self.assertEqual(response.data["category_name"], "Toll Roads")

    def test_list_returns_paginated_results(self):
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("50.00"),
            expense_date="2026-01-01",
            created_by=self.user,
        )
        response = self.client.get(self.BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_category_code(self):
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.fuel_cat,
            amount=Decimal("100.00"),
            expense_date="2026-01-01",
            created_by=self.user,
        )
        Expense.objects.create(
            vehicle=self.vehicle,
            category=self.washing_cat,
            amount=Decimal("30.00"),
            expense_date="2026-01-02",
            created_by=self.user,
        )
        response = self.client.get(f"{self.BASE_URL}?category_code=FUEL")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["category_code"], "FUEL")

    def test_patch_updates_amount(self):
        expense = Expense.objects.create(
            vehicle=self.vehicle,
            category=self.other_cat,
            amount=Decimal("50.00"),
            expense_date="2026-01-01",
            created_by=self.user,
        )
        url = f"{self.BASE_URL}{expense.id}/"
        response = self.client.patch(url, {"amount": "75.00"}, format="multipart")
        self.assertEqual(response.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal("75.00"))

    def test_delete_cascades_parts(self):
        expense = Expense.objects.create(
            vehicle=self.vehicle,
            category=self.parts_cat,
            amount=Decimal("100.00"),
            expense_date="2026-01-01",
            created_by=self.user,
        )
        ExpensePart.objects.create(
            expense=expense, name="Filter", quantity=1, unit_price=Decimal("25.00")
        )
        url = f"{self.BASE_URL}{expense.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ExpensePart.objects.exists())

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.BASE_URL)
        self.assertEqual(response.status_code, 401)

    def test_categories_endpoint_returns_active_only(self):
        inactive = ExpenseCategory.objects.create(
            name="Disabled", is_active=False, order=99
        )
        response = self.client.get(f"{self.BASE_URL}categories/")
        self.assertEqual(response.status_code, 200)
        ids = [c["id"] for c in response.data]
        self.assertNotIn(str(inactive.id), ids)
        self.assertIn(str(self.fuel_cat.id), ids)

    def test_inspection_expense_auto_creates_technical_inspection(self):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.inspection_cat.id),
            "expense_date": "2026-03-01",
            "inspection_date": "2026-03-01",
            "next_inspection_date": "2028-03-01",
            "official_cost": "99.00",
            "additional_cost": "50.00",
        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        inspections = TechnicalInspection.objects.filter(vehicle=self.vehicle)
        self.assertEqual(inspections.count(), 1)
        ins = inspections.first()
        self.assertEqual(str(ins.inspection_date), "2026-03-01")
        self.assertEqual(str(ins.next_inspection_date), "2028-03-01")

    def test_delete_inspection_expense_deletes_linked_inspection(self):
        payload = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.inspection_cat.id),
            "expense_date": "2026-03-01",
            "inspection_date": "2026-03-01",
            "official_cost": "100.00",
        }
        response = self.client.post(self.BASE_URL, payload, format="multipart")
        expense_id = response.data["id"]
        self.assertEqual(TechnicalInspection.objects.count(), 1)
        self.client.delete(f"{self.BASE_URL}{expense_id}/")
        self.assertEqual(TechnicalInspection.objects.count(), 0)
