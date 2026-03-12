"""
Fuel types multi-select tests.
===============================
Covers: multi-type selection, JSON parsing from FormData, invalid type
validation, empty list rejection, PATCH update of fuel_types.
"""

import json

from django.test import TestCase
from rest_framework.test import APIClient

from expense.models import Expense, ExpenseCategory, FuelExpenseDetail

from .helpers import authenticate, make_user, make_vehicle

FMT = "multipart"


class FuelTypesCreateTest(TestCase):
    """POST /expense/ — fuel_types field validation."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )

    def _payload(self, **overrides):
        base = {
            "vehicle": str(self.vehicle.id),
            "category": str(self.fuel_cat.id),
            "amount": "100.00",
            "expense_date": "2026-03-01",
            "fuel_types": json.dumps(["DIESEL"]),
        }
        base.update(overrides)
        return base

    def test_single_fuel_type_returns_201(self):
        response = self.client.post(self.BASE_URL, self._payload(), format=FMT)
        self.assertEqual(response.status_code, 201)
        detail = FuelExpenseDetail.objects.get(expense_id=response.data["id"])
        self.assertEqual(detail.fuel_types, ["DIESEL"])

    def test_multiple_fuel_types_returns_201(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps(["DIESEL", "LPG"])),
            format=FMT,
        )
        self.assertEqual(response.status_code, 201)
        detail = FuelExpenseDetail.objects.get(expense_id=response.data["id"])
        self.assertCountEqual(detail.fuel_types, ["DIESEL", "LPG"])

    def test_all_four_fuel_types_accepted(self):
        all_types = ["GASOLINE", "DIESEL", "LPG", "ELECTRIC"]
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps(all_types)),
            format=FMT,
        )
        self.assertEqual(response.status_code, 201)
        detail = FuelExpenseDetail.objects.get(expense_id=response.data["id"])
        self.assertCountEqual(detail.fuel_types, all_types)

    def test_empty_fuel_types_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps([])),
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fuel_types", response.data)

    def test_missing_fuel_types_returns_400(self):
        payload = self._payload()
        del payload["fuel_types"]
        response = self.client.post(self.BASE_URL, payload, format=FMT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("fuel_types", response.data)

    def test_invalid_fuel_type_value_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps(["HYDROGEN"])),
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fuel_types", str(response.data))

    def test_mixed_valid_and_invalid_types_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps(["DIESEL", "KEROSENE"])),
            format=FMT,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fuel_types", str(response.data))

    def test_plain_string_parsed_as_single_type(self):
        """FormData may send a plain string instead of JSON array."""
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types="GASOLINE"),
            format=FMT,
        )
        self.assertEqual(response.status_code, 201)
        detail = FuelExpenseDetail.objects.get(expense_id=response.data["id"])
        self.assertEqual(detail.fuel_types, ["GASOLINE"])

    def test_response_contains_fuel_types_list(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(fuel_types=json.dumps(["DIESEL", "LPG"])),
            format=FMT,
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsInstance(response.data["fuel_types"], list)
        self.assertCountEqual(response.data["fuel_types"], ["DIESEL", "LPG"])


class FuelTypesPatchTest(TestCase):
    """PATCH /expense/{id}/ — update fuel_types on existing expense."""

    BASE_URL = "/api/v1/expense/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.fuel_cat, _ = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )
        response = self.client.post(
            self.BASE_URL,
            {
                "vehicle": str(self.vehicle.id),
                "category": str(self.fuel_cat.id),
                "amount": "100.00",
                "expense_date": "2026-03-01",
                "fuel_types": json.dumps(["DIESEL"]),
            },
            format="multipart",
        )
        self.expense_id = response.data["id"]

    def test_patch_fuel_types_updates_detail(self):
        response = self.client.patch(
            f"{self.BASE_URL}{self.expense_id}/",
            {"fuel_types": json.dumps(["LPG", "ELECTRIC"])},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        detail = FuelExpenseDetail.objects.get(expense_id=self.expense_id)
        self.assertCountEqual(detail.fuel_types, ["LPG", "ELECTRIC"])
