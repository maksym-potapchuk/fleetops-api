"""
Vehicle Owner API Tests
========================
Covers: assign owner (POST /owner/), get current owner (GET /owner/),
        update agreement (PATCH /owner/), unassign (DELETE /owner/),
        ownership history (GET /owner/history/), PROTECT constraint.
"""

from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.models import OwnerHistory, VehicleOwner

from .helpers import authenticate, make_driver, make_user, make_vehicle


class VehicleOwnerAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="owner@example.com", username="ownuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.driver = make_driver()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/owner/"

    def test_assign_owner_returns_201(self):
        response = self.client.post(
            self.url,
            {"driver": str(self.driver.id), "agreement_number": "AGR-001"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(VehicleOwner.objects.count(), 1)

    def test_response_flattens_driver(self):
        response = self.client.post(
            self.url, {"driver": str(self.driver.id)}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["driver"]["first_name"], "Jan")
        self.assertEqual(response.data["driver"]["last_name"], "Kowalski")

    def test_get_current_owner(self):
        VehicleOwner.objects.create(vehicle=self.vehicle, driver=self.driver)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["driver"]["id"], str(self.driver.id))

    def test_get_no_owner_returns_null(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data)

    def test_patch_agreement_number(self):
        VehicleOwner.objects.create(vehicle=self.vehicle, driver=self.driver)
        response = self.client.patch(
            self.url, {"agreement_number": "AGR-NEW"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        owner = VehicleOwner.objects.get(vehicle=self.vehicle)
        self.assertEqual(owner.agreement_number, "AGR-NEW")

    def test_delete_unassigns_owner(self):
        VehicleOwner.objects.create(vehicle=self.vehicle, driver=self.driver)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(VehicleOwner.objects.filter(vehicle=self.vehicle).exists())
        self.assertEqual(OwnerHistory.objects.filter(vehicle=self.vehicle).count(), 1)

    def test_ownership_history_returns_archived_records(self):
        from vehicle.services import assign_owner

        driver_b = make_driver(
            first_name="Anna", last_name="Nowak", phone_number="48222222222"
        )
        assign_owner(self.vehicle, self.driver, agreement_number="AGR-1")
        assign_owner(self.vehicle, driver_b, agreement_number="AGR-2")
        response = self.client.get(f"{self.url}history/")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["driver"]["id"], str(self.driver.id))

    def test_driver_protect_prevents_delete(self):
        VehicleOwner.objects.create(vehicle=self.vehicle, driver=self.driver)
        with self.assertRaises(ProtectedError):
            self.driver.delete()

    def test_cascade_on_vehicle_delete(self):
        VehicleOwner.objects.create(vehicle=self.vehicle, driver=self.driver)
        self.vehicle.delete()
        self.assertEqual(VehicleOwner.objects.count(), 0)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
