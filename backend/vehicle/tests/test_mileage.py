"""
Mileage Log API Tests
=====================
Covers: POST /vehicle/{pk}/mileage/, GET list, validation, side effects.

Key business rules:
- km must be strictly greater than vehicle.initial_km
- POST updates vehicle.initial_km to the new value
- List is NOT paginated (plain array)
- Cascade delete when vehicle is hard-deleted
"""

from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.models import MileageLog

from .helpers import authenticate, make_user, make_vehicle


class MileageLogAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="mileage@example.com", username="mlguser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()
        self.url = f"/api/v1/vehicle/{self.vehicle.id}/mileage/"

    def _payload(self, **overrides):
        base = {"km": 500, "recorded_at": "2026-03-01"}
        base.update(overrides)
        return base

    # --- happy path ---

    def test_create_mileage_returns_201(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MileageLog.objects.count(), 1)

    def test_create_updates_vehicle_initial_km(self):
        """After logging mileage, vehicle.initial_km must be updated to the new value."""
        self.client.post(self.url, self._payload(km=1500), format="json")
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.initial_km, 1500)

    def test_sequential_mileage_entries_update_km_correctly(self):
        """Each new entry must exceed the previous, and vehicle.initial_km tracks the latest."""
        self.client.post(self.url, self._payload(km=1000), format="json")
        self.client.post(
            self.url, self._payload(km=2000, recorded_at="2026-03-02"), format="json"
        )
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.initial_km, 2000)
        self.assertEqual(MileageLog.objects.count(), 2)

    # --- validation ---

    def test_km_equal_to_initial_returns_400(self):
        """km must be STRICTLY greater, not equal."""
        self.vehicle.initial_km = 500
        self.vehicle.save(update_fields=["initial_km"])
        response = self.client.post(self.url, self._payload(km=500), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("km", response.data)

    def test_km_less_than_initial_returns_400(self):
        self.vehicle.initial_km = 1000
        self.vehicle.save(update_fields=["initial_km"])
        response = self.client.post(self.url, self._payload(km=500), format="json")
        self.assertEqual(response.status_code, 400)

    def test_km_zero_on_zero_initial_returns_400(self):
        """Edge case: vehicle starts at 0, logging 0 must be rejected (not strictly greater)."""
        response = self.client.post(self.url, self._payload(km=0), format="json")
        self.assertEqual(response.status_code, 400)

    # --- list ---

    def test_list_returns_plain_array(self):
        """Mileage list is NOT paginated — returns plain array, no {results: []}."""
        MileageLog.objects.create(
            vehicle=self.vehicle, km=100, recorded_at="2026-01-01"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)

    # --- cascade ---

    def test_cascade_delete_removes_mileage_logs(self):
        MileageLog.objects.create(
            vehicle=self.vehicle, km=100, recorded_at="2026-01-01"
        )
        self.vehicle.delete()
        self.assertEqual(MileageLog.objects.count(), 0)

    # --- auth ---

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
