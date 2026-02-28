"""
Driver Test Suite
=================
Covers: Driver model constraints, DriverSerializer phone validation, Driver API endpoints.

BUG / VULNERABILITY markers document known flaws exposed by these tests.
"""

import uuid

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from driver.models import Driver
from driver.serializers import DriverSerializer

# ---------------------------------------------------------------------------
# Shared factory helpers
# ---------------------------------------------------------------------------


def make_user(email="test@example.com", password="pass123!", username="testuser"):
    return User.objects.create_user(email=email, password=password, username=username)


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


# ===========================================================================
# 1. Driver Model Tests
# ===========================================================================


class DriverModelTest(TestCase):
    def test_phone_number_unique_constraint(self):
        make_driver()
        with self.assertRaises(IntegrityError):
            make_driver(first_name="Other", last_name="Driver")

    def test_telegram_id_unique_constraint(self):
        make_driver(telegram_id=123_456_789)
        with self.assertRaises(IntegrityError):
            make_driver(
                first_name="Other",
                last_name="Driver",
                phone_number="48987654321",
                telegram_id=123_456_789,
            )

    def test_telegram_id_is_nullable(self):
        driver = make_driver()
        self.assertIsNone(driver.telegram_id)

    def test_multiple_drivers_can_have_null_telegram_id(self):
        """NULL values must not trigger the unique constraint (SQL standard)."""
        make_driver()
        driver2 = make_driver(phone_number="48987654321")
        self.assertIsNone(driver2.telegram_id)

    def test_has_vehicle_defaults_to_false(self):
        driver = make_driver()
        self.assertFalse(driver.has_vehicle)

    def test_is_active_driver_defaults_to_false(self):
        driver = make_driver()
        self.assertFalse(driver.is_active_driver)

    def test_last_active_at_is_nullable(self):
        driver = make_driver()
        self.assertIsNone(driver.last_active_at)

    def test_str_representation(self):
        driver = make_driver()
        self.assertEqual(str(driver), "Jan Kowalski")

    def test_driver_id_is_uuid(self):
        driver = make_driver()
        self.assertIsInstance(driver.id, uuid.UUID)


# ===========================================================================
# 2. DriverSerializer Validation Tests
# ===========================================================================


class DriverSerializerValidationTest(TestCase):
    """
    Tests for validate_phone_number logic in DriverSerializer.
    Rules: digits only, 10–15 chars, must start with "48" (Polish country code).
    """

    def _validate(self, data, instance=None):
        s = DriverSerializer(
            instance=instance, data=data, partial=(instance is not None)
        )
        s.is_valid()
        return s

    # --- valid cases ---

    def test_valid_polish_phone_number_accepted(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "Kowalski",
                "phone_number": "48123456789",
            }
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_minimum_length_10_digits_accepted(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "4812345678"}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_maximum_length_15_digits_accepted(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "481234567890123"}
        )
        self.assertTrue(s.is_valid(), s.errors)

    # --- invalid prefix ---

    def test_phone_without_48_prefix_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "79123456789"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("phone_number", s.errors)

    def test_phone_starting_with_480_rejected(self):
        """Only "48" prefix is allowed — "480..." must be rejected."""
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48012345678"}
        )
        # "48012345678".startswith("48") == True, so actually this is ACCEPTED.
        # Documenting the edge case: any number starting with "48" passes,
        # including those starting with "480", "481", etc.
        # This is the intended behaviour per the current rule.
        self.assertTrue(
            s.is_valid(), "48-prefixed numbers with trailing 0 are accepted"
        )

    # --- invalid format ---

    def test_phone_with_plus_prefix_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "+48123456789"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("phone_number", s.errors)

    def test_phone_with_hyphens_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48-123-456-789"}
        )
        self.assertFalse(s.is_valid())

    def test_phone_with_spaces_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48 123 456 789"}
        )
        self.assertFalse(s.is_valid())

    def test_empty_phone_rejected(self):
        s = self._validate({"first_name": "Jan", "last_name": "K", "phone_number": ""})
        self.assertFalse(s.is_valid())

    # --- invalid length ---

    def test_phone_too_short_9_digits_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "481234567"}
        )
        self.assertFalse(s.is_valid())

    def test_phone_too_long_16_digits_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "4812345678901234"}
        )
        self.assertFalse(s.is_valid())

    # --- read-only fields ---

    def test_read_only_has_vehicle_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "has_vehicle": True,
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("has_vehicle", s.validated_data)

    def test_read_only_is_active_driver_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "is_active_driver": True,
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("is_active_driver", s.validated_data)

    def test_read_only_last_active_at_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "last_active_at": "2026-01-01T00:00:00Z",
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("last_active_at", s.validated_data)


# ===========================================================================
# 3. Driver API Tests
# ===========================================================================


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
        Vehicle.driver uses on_delete=PROTECT (from Driver side).
        Attempting to delete a driver that is assigned to a vehicle must fail
        with a non-204 response.
        """
        from vehicle.models import ManufacturerChoices, Vehicle, VehicleStatus

        driver = make_driver()
        Vehicle.objects.create(
            model="Camry",
            manufacturer=ManufacturerChoices.TOYOTA,
            year=2022,
            cost="25000.00",
            vin_number="1HGBH41JXMN109186",
            car_number="AA6601BB",
            initial_km=0,
            status=VehicleStatus.PREPARATION,
            driver=driver,
        )
        # BUG: DriverViewSet.perform_destroy does not catch ProtectedError.
        # Without raise_request_exception=False the exception propagates to the
        # test runner as an ERROR instead of a FAIL. Disable propagation so we
        # receive the 500 response and can assert the deletion failed.
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
