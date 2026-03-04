"""
Technical Inspection API Tests
==============================
Covers: CRUD operations, validation, and Vehicle serializer annotation fields.
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import TechnicalInspection, Vehicle


def make_user(email="insp@example.com", password="pass123!", username="inspuser"):
    return User.objects.create_user(email=email, password=password, username=username)


def make_vehicle(**kwargs):
    defaults = {
        "model": "Camry",
        "manufacturer": ManufacturerChoices.TOYOTA,
        "year": 2022,
        "cost": "25000.00",
        "vin_number": "1HGBH41JXMN109186",
        "car_number": "AA6601BB",
        "color": "#FFFFFF",
        "initial_km": 0,
        "status": VehicleStatus.PREPARATION,
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)


class TechnicalInspectionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.base_url = f"/api/v1/vehicle/{self.vehicle.id}/inspections/"

    def _payload(self, **overrides):
        base = {"inspection_date": "2025-06-15"}
        base.update(overrides)
        return base

    def test_create_returns_201(self):
        response = self.client.post(self.base_url, self._payload(), format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["inspection_date"], "2025-06-15")

    def test_create_auto_calculates_next_inspection_date(self):
        response = self.client.post(self.base_url, self._payload(), format="multipart")
        self.assertEqual(response.data["next_inspection_date"], "2026-06-15")
        self.assertEqual(response.data["expiry_date"], "2026-06-15")

    def test_create_with_custom_next_inspection_date(self):
        payload = self._payload(next_inspection_date="2027-06-15")
        response = self.client.post(self.base_url, payload, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["next_inspection_date"], "2027-06-15")

    def test_list_returns_inspections_ordered_desc(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2024, 1, 1)
        )
        TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2025, 6, 15)
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["inspection_date"], "2025-06-15")
        self.assertEqual(results[1]["inspection_date"], "2024-01-01")

    def test_patch_updates_notes(self):
        ins = TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2025, 3, 1)
        )
        url = f"{self.base_url}{ins.pk}/"
        response = self.client.patch(url, {"notes": "Updated"}, format="multipart")
        self.assertEqual(response.status_code, 200)
        ins.refresh_from_db()
        self.assertEqual(ins.notes, "Updated")

    def test_delete_returns_204(self):
        ins = TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2025, 3, 1)
        )
        url = f"{self.base_url}{ins.pk}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(TechnicalInspection.objects.filter(pk=ins.pk).exists())

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.base_url)
        self.assertEqual(response.status_code, 401)

    def test_vehicle_detail_includes_inspection_fields(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2025, 6, 15)
        )
        response = self.client.get(f"/api/v1/vehicle/{self.vehicle.id}/")
        self.assertEqual(response.data["last_inspection_date"], "2025-06-15")
        self.assertEqual(response.data["next_inspection_date"], "2026-06-15")
        self.assertIsInstance(response.data["days_until_inspection"], int)

    def test_vehicle_without_inspections_has_null_fields(self):
        response = self.client.get(f"/api/v1/vehicle/{self.vehicle.id}/")
        self.assertIsNone(response.data["last_inspection_date"])
        self.assertIsNone(response.data["next_inspection_date"])
        self.assertIsNone(response.data["days_until_inspection"])

    def test_cascade_delete_removes_inspections(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle, inspection_date=datetime.date(2025, 1, 1)
        )
        vehicle_id = self.vehicle.id
        self.vehicle.delete()
        self.assertEqual(
            TechnicalInspection.objects.filter(vehicle_id=vehicle_id).count(), 0
        )
