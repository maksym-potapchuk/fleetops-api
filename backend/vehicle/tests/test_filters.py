"""
Backend filter tests — vehicle, expense, schema filters.
Verifies filter params, combinations, empty results, SQL injection safety,
ordering, and invalid values.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User
from expense.models import Expense, ExpenseCategory
from fleet_management.models import (
    FleetVehicleRegulationItem,
    FleetVehicleRegulationSchema,
)
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle


def _make_user():
    return User.objects.create_user(
        email="filter@test.com", password="pass123!", username="filtertest"
    )


def _auth(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken
    client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)


class VehicleFilterTest(TestCase):
    """GET /api/v1/vehicle/?status=X&manufacturer=Y..."""

    URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()
        _auth(self.client, self.user)
        for i in range(5):
            Vehicle.objects.create(
                model="Camry", manufacturer=ManufacturerChoices.TOYOTA,
                year=2022, cost="25000", vin_number=f"VFRT{i:013d}",
                car_number=f"RT{i:04d}XX", color="#FFF",
                status=VehicleStatus.READY,
            )
        for i in range(3):
            Vehicle.objects.create(
                model="X5", manufacturer="BMW",
                year=2023, cost="50000", vin_number=f"VFAB{i:013d}",
                car_number=f"AB{i:04d}XX", color="#000",
                status=VehicleStatus.AUCTION,
            )
        for i in range(2):
            Vehicle.objects.create(
                model="Corolla", manufacturer=ManufacturerChoices.TOYOTA,
                year=2021, cost="18000", vin_number=f"VFST{i:013d}",
                car_number=f"ST{i:04d}XX", color="#AAA",
                status=VehicleStatus.SERVICE,
            )

    def test_filter_by_status(self):
        res = self.client.get(f"{self.URL}?status=READY")
        self.assertEqual(res.data["count"], 5)

    def test_filter_by_manufacturer(self):
        res = self.client.get(f"{self.URL}?manufacturer=BMW")
        self.assertEqual(res.data["count"], 3)

    def test_filter_by_year(self):
        res = self.client.get(f"{self.URL}?year=2021")
        self.assertEqual(res.data["count"], 2)

    def test_no_match_returns_empty(self):
        res = self.client.get(f"{self.URL}?status=SOLD")
        self.assertEqual(res.data["count"], 0)

    def test_sql_injection_rejected(self):
        res = self.client.get(f"{self.URL}?status=READY' OR 1=1 --")
        # DjangoFilterBackend rejects or returns 0 — both safe
        self.assertIn(res.status_code, [200, 400])
        if res.status_code == 200:
            count = res.data.get("count", len(res.data.get("results", res.data)))
            self.assertLessEqual(count, 5)


class ExpenseFilterTest(TestCase):
    """GET /api/v1/expense/?category_code=X&date_from=Y..."""

    URL = "/api/v1/expense/"

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()
        _auth(self.client, self.user)
        self.vehicle = Vehicle.objects.create(
            model="Test", manufacturer=ManufacturerChoices.TOYOTA,
            year=2022, cost="20000", vin_number="EXPFILT000000001",
            car_number="EF0001XX", color="#FFF", status=VehicleStatus.AUCTION,
        )
        self.fuel_cat = ExpenseCategory.objects.get_or_create(
            code="FUEL", defaults={"name": "Fuel", "is_system": True, "order": 1}
        )[0]
        self.other_cat = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )[0]
        for i in range(5):
            Expense.objects.create(
                vehicle=self.vehicle, category=self.fuel_cat,
                expense_date=f"2026-01-{i + 1:02d}T12:00:00Z",
                amount=Decimal("100.00"), payment_method="CASH",
                payer_type="COMPANY", created_by=self.user,
            )
        for i in range(3):
            Expense.objects.create(
                vehicle=self.vehicle, category=self.other_cat,
                expense_date=f"2026-03-{i + 1:02d}T12:00:00Z",
                amount=Decimal("250.00"), payment_method="CASHLESS",
                payer_type="COMPANY", created_by=self.user,
            )
        for i in range(2):
            Expense.objects.create(
                vehicle=self.vehicle, category=self.fuel_cat,
                expense_date=f"2026-06-{i + 1:02d}T12:00:00Z",
                amount=Decimal("500.00"), payment_method="CASH",
                payer_type="COMPANY", created_by=self.user,
            )

    def test_filter_by_category_code(self):
        res = self.client.get(f"{self.URL}?category_code=FUEL")
        self.assertEqual(res.data["count"], 7)

    def test_filter_by_payment_method(self):
        res = self.client.get(f"{self.URL}?payment_method=CASHLESS")
        self.assertEqual(res.data["count"], 3)

    def test_filter_by_date_range(self):
        res = self.client.get(f"{self.URL}?date_from=2026-02-01&date_to=2026-04-30")
        self.assertEqual(res.data["count"], 3)

    def test_filter_by_min_amount(self):
        res = self.client.get(f"{self.URL}?min_amount=200")
        self.assertEqual(res.data["count"], 5)

    def test_filter_by_max_amount(self):
        res = self.client.get(f"{self.URL}?max_amount=150")
        self.assertEqual(res.data["count"], 5)

    def test_combined_category_and_date(self):
        res = self.client.get(f"{self.URL}?category_code=FUEL&date_from=2026-05-01")
        self.assertEqual(res.data["count"], 2)

    def test_invalid_date_returns_400(self):
        res = self.client.get(f"{self.URL}?date_from=not-a-date")
        self.assertEqual(res.status_code, 400)

    def test_sql_injection_in_category_code(self):
        res = self.client.get(f"{self.URL}?category_code=FUEL' OR 1=1 --")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)


class SchemaFilterTest(TestCase):
    """GET /api/v1/fleet/regulation/schemas/?title=X&is_default=Y"""

    URL = "/api/v1/fleet/regulation/schemas/"

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()
        _auth(self.client, self.user)
        s1 = FleetVehicleRegulationSchema.objects.create(
            title="Basic Regulation", is_default=True
        )
        FleetVehicleRegulationItem.objects.create(
            schema=s1, title="Oil", every_km=10000
        )
        FleetVehicleRegulationItem.objects.create(
            schema=s1, title="Brakes", every_km=30000
        )
        s2 = FleetVehicleRegulationSchema.objects.create(title="Advanced Package")
        FleetVehicleRegulationItem.objects.create(
            schema=s2, title="Full Service", every_km=50000
        )

    def test_filter_by_title_icontains(self):
        res = self.client.get(f"{self.URL}?title=basic")
        self.assertEqual(res.data["count"], 1)

    def test_filter_by_is_default_true(self):
        res = self.client.get(f"{self.URL}?is_default=true")
        self.assertEqual(res.data["count"], 1)

    def test_filter_by_is_default_false(self):
        res = self.client.get(f"{self.URL}?is_default=false")
        self.assertEqual(res.data["count"], 1)

    def test_no_match(self):
        res = self.client.get(f"{self.URL}?title=nonexistent")
        self.assertEqual(res.data["count"], 0)


class ExpenseOrderingTest(TestCase):
    """Test ordering params on expense endpoint."""

    URL = "/api/v1/expense/"

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()
        _auth(self.client, self.user)
        self.vehicle = Vehicle.objects.create(
            model="T", manufacturer=ManufacturerChoices.TOYOTA,
            year=2022, cost="20000", vin_number="ORDVIN0000000001",
            car_number="OR0001XX", color="#FFF", status=VehicleStatus.AUCTION,
        )
        cat = ExpenseCategory.objects.get_or_create(
            code="OTHER", defaults={"name": "Other", "is_system": True, "order": 7}
        )[0]
        for i, amt in enumerate([300, 100, 500, 200]):
            Expense.objects.create(
                vehicle=self.vehicle, category=cat,
                expense_date=f"2026-0{i + 1}-15T12:00:00Z",
                amount=Decimal(str(amt)), payer_type="COMPANY",
                created_by=self.user,
            )

    def test_ordering_by_amount_asc(self):
        res = self.client.get(f"{self.URL}?ordering=amount")
        amounts = [float(e["amount"]) for e in res.data["results"]]
        self.assertEqual(amounts, sorted(amounts))

    def test_ordering_by_amount_desc(self):
        res = self.client.get(f"{self.URL}?ordering=-amount")
        amounts = [float(e["amount"]) for e in res.data["results"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_ordering_by_date_asc(self):
        res = self.client.get(f"{self.URL}?ordering=expense_date")
        dates = [e["expense_date"] for e in res.data["results"]]
        self.assertEqual(dates, sorted(dates))
