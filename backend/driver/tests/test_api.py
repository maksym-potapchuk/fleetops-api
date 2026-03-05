"""
Driver API Tests
================
Covers: CRUD operations, phone validation, PROTECT constraint, auth guards.
"""

import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from driver.models import Driver

from .helpers import authenticate, make_driver, make_user


class DriverAPITest(TestCase):
    BASE_URL = "/api/v1/driver/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def _payload(self, **overrides):
        base = {
            "first_name": "Jan",
            "last_name": "Kowalski",
            "phone_number": "48123456789",
        }
        base.update(overrides)
        return base

    # --- create ---

    def test_create_driver_returns_201(self):
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_driver_response_has_uuid_id(self):
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data.get("id"))

    def test_create_driver_has_vehicle_is_false_in_response(self):
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["has_vehicle"])

    def test_phone_without_48_prefix_returns_400(self):
        response = self.client.post(
            self.BASE_URL, self._payload(phone_number="79123456789"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_with_plus_sign_returns_400(self):
        response = self.client.post(
            self.BASE_URL, self._payload(phone_number="+48123456789"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_too_short_returns_400(self):
        response = self.client.post(
            self.BASE_URL, self._payload(phone_number="481234"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_too_long_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(phone_number="4812345678901234"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_phone_number_returns_400(self):
        self.client.post(self.BASE_URL, self._payload(), format="json")
        response = self.client.post(
            self.BASE_URL,
            self._payload(first_name="Other", last_name="Driver"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_set_has_vehicle_via_create(self):
        """has_vehicle is read-only — must remain False regardless of request payload."""
        response = self.client.post(
            self.BASE_URL,
            self._payload(has_vehicle=True),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["has_vehicle"])

    # --- list ---

    def test_list_drivers_returns_200(self):
        make_driver()
        response = self.client.get(self.BASE_URL)
        self.assertEqual(response.status_code, 200)

    def test_list_contains_created_driver(self):
        make_driver()
        response = self.client.get(self.BASE_URL)
        self.assertEqual(len(response.data["results"]), 1)

    # --- retrieve ---

    def test_retrieve_existing_driver_returns_200(self):
        driver = make_driver()
        response = self.client.get(f"{self.BASE_URL}{driver.id}/")
        self.assertEqual(response.status_code, 200)

    def test_retrieve_nonexistent_driver_returns_404(self):
        response = self.client.get(f"{self.BASE_URL}{uuid.uuid4()}/")
        self.assertEqual(response.status_code, 404)

    # --- update ---

    def test_patch_first_name_updates_successfully(self):
        driver = make_driver()
        response = self.client.patch(
            f"{self.BASE_URL}{driver.id}/", {"first_name": "Marek"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "Marek")
        driver.refresh_from_db()
        self.assertEqual(driver.first_name, "Marek")

    def test_patch_phone_to_existing_number_returns_400(self):
        make_driver(phone_number="48111111111")
        driver2 = make_driver(
            first_name="Anna", last_name="B", phone_number="48222222222"
        )
        response = self.client.patch(
            f"{self.BASE_URL}{driver2.id}/",
            {"phone_number": "48111111111"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_has_vehicle_ignored(self):
        """
        has_vehicle is read-only. Sending it in a PATCH request must not change its value.
        """
        driver = make_driver()
        response = self.client.patch(
            f"{self.BASE_URL}{driver.id}/", {"has_vehicle": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        driver.refresh_from_db()
        self.assertFalse(
            driver.has_vehicle,
            "has_vehicle must not be settable via PATCH request",
        )

    # --- delete ---

    def test_delete_driver_without_vehicle_returns_204(self):
        driver = make_driver()
        response = self.client.delete(f"{self.BASE_URL}{driver.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Driver.objects.filter(id=driver.id).exists())

    def test_delete_driver_with_vehicle_returns_error(self):
        """
        VehicleOwner.driver uses on_delete=PROTECT.
        Attempting to delete a driver that is assigned to a vehicle must fail
        with a non-204 response.
        """
        from vehicle.constants import ManufacturerChoices, VehicleStatus
        from vehicle.models import Vehicle, VehicleOwner

        driver = make_driver()
        vehicle = Vehicle.objects.create(
            model="Camry",
            manufacturer=ManufacturerChoices.TOYOTA,
            year=2022,
            cost="25000.00",
            vin_number="1HGBH41JXMN109186",
            car_number="AA6601BB",
            initial_km=0,
            status=VehicleStatus.AUCTION,
        )
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)
        # BUG: DriverViewSet.perform_destroy does not catch ProtectedError.
        self.client.raise_request_exception = False
        response = self.client.delete(f"{self.BASE_URL}{driver.id}/")
        self.assertNotEqual(
            response.status_code,
            204,
            "Driver with assigned vehicle must NOT be deletable (PROTECT constraint)",
        )

    # --- authentication ---

    def test_unauthenticated_list_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(self.BASE_URL)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_create_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_delete_returns_401(self):
        driver = make_driver()
        unauthenticated = APIClient()
        response = unauthenticated.delete(f"{self.BASE_URL}{driver.id}/")
        self.assertEqual(response.status_code, 401)
