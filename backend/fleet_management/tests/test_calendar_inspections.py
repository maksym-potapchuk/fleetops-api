"""
CalendarInspections API Tests
==============================
Covers: GET /fleet/calendar-inspections/ — returns the latest inspection
per vehicle with non-null next_inspection_date, ordered ascending.
"""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.models import TechnicalInspection

from .helpers import authenticate, make_user, make_vehicle


class CalendarInspectionsAPITest(TestCase):
    URL = "/api/v1/fleet/calendar-inspections/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()

    def test_returns_latest_inspection_per_vehicle(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date(2024, 1, 1),
            next_inspection_date=date(2025, 1, 1),
            created_by=self.user,
        )
        latest = TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date(2025, 3, 1),
            next_inspection_date=date(2026, 3, 1),
            created_by=self.user,
        )

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], latest.id)
        self.assertEqual(results[0]["planned_at"], "2026-03-01")

    def test_excludes_inspections_with_null_next_date(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date(2025, 1, 1),
            next_inspection_date=None,
            created_by=self.user,
        )

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 0)

    def test_orders_by_next_inspection_date_ascending(self):
        v2 = make_vehicle(
            car_number="BB0002CC",
            vin_number="VIN_INSP_ORD_002",
        )
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date(2025, 6, 1),
            next_inspection_date=date(2026, 6, 1),
            created_by=self.user,
        )
        TechnicalInspection.objects.create(
            vehicle=v2,
            inspection_date=date(2025, 2, 1),
            next_inspection_date=date(2026, 2, 1),
            created_by=self.user,
        )

        response = self.client.get(self.URL)

        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["planned_at"], "2026-02-01")
        self.assertEqual(results[1]["planned_at"], "2026-06-01")

    def test_response_contains_vehicle_fields(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date(2025, 1, 1),
            next_inspection_date=date(2026, 1, 1),
            created_by=self.user,
        )

        response = self.client.get(self.URL)

        entry = response.data["results"][0]
        self.assertEqual(entry["vehicle"], str(self.vehicle.id))
        self.assertEqual(entry["vehicle_car_number"], self.vehicle.car_number)

    def test_unauthenticated_returns_401(self):
        self.client.cookies.clear()

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 401)
