"""
Vehicle Owner History API Tests
================================
Covers: assign owner, release, list, PROTECT constraint on driver deletion.
"""

from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from driver.models import Driver
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle, VehicleOwnerHistory


def make_user(email="owner@example.com", password="pass123!", username="ownuser"):
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


def make_driver(**kwargs):
    defaults = {
        "first_name": "Jan",
        "last_name": "Kowalski",
        "phone_number": "48123456789",
    }
    defaults.update(kwargs)
    return Driver.objects.create(**defaults)


def authenticate(client: APIClient, user: User) -> None:
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)


class VehicleOwnerHistoryAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.driver = make_driver()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/owner-history/"

    def test_assign_owner_returns_201(self):
        response = self.client.post(
            self.url,
            {"driver": str(self.driver.id), "agreement_number": "AGR-001"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(VehicleOwnerHistory.objects.count(), 1)

    def test_response_flattens_driver(self):
        """to_representation must flatten driver to {id, first_name, last_name}."""
        response = self.client.post(
            self.url, {"driver": str(self.driver.id)}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["driver"]["first_name"], "Jan")
        self.assertEqual(response.data["driver"]["last_name"], "Kowalski")

    def test_list_returns_owner_records(self):
        VehicleOwnerHistory.objects.create(vehicle=self.vehicle, driver=self.driver)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_patch_released_at_closes_ownership(self):
        history = VehicleOwnerHistory.objects.create(
            vehicle=self.vehicle, driver=self.driver
        )
        url = f"{self.url}{history.pk}/"
        response = self.client.patch(
            url, {"released_at": "2026-03-01T12:00:00Z"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        history.refresh_from_db()
        self.assertIsNotNone(history.released_at)

    def test_patch_agreement_number(self):
        history = VehicleOwnerHistory.objects.create(
            vehicle=self.vehicle, driver=self.driver
        )
        url = f"{self.url}{history.pk}/"
        response = self.client.patch(
            url, {"agreement_number": "AGR-NEW"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        history.refresh_from_db()
        self.assertEqual(history.agreement_number, "AGR-NEW")

    def test_driver_protect_prevents_delete(self):
        """Driver with owner history cannot be deleted (PROTECT)."""
        VehicleOwnerHistory.objects.create(vehicle=self.vehicle, driver=self.driver)
        with self.assertRaises(ProtectedError):
            self.driver.delete()

    def test_cascade_on_vehicle_delete(self):
        VehicleOwnerHistory.objects.create(vehicle=self.vehicle, driver=self.driver)
        self.vehicle.delete()
        self.assertEqual(VehicleOwnerHistory.objects.count(), 0)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
