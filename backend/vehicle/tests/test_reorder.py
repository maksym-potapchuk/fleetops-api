"""
Vehicle Reorder API Tests
=========================
POST /vehicle/reorder/ — batch update status_position (and optionally status).
"""

from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.constants import VehicleStatus

from .helpers import authenticate, make_user, make_vehicle


class VehicleReorderAPITest(TestCase):
    URL = "/api/v1/vehicle/reorder/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="reorder@example.com", username="reorduser")
        authenticate(self.client, self.user)
        self.v1 = make_vehicle(
            car_number="RE0001AA", vin_number="VIN00000000000RE1", status_position=1000
        )
        self.v2 = make_vehicle(
            car_number="RE0002AA", vin_number="VIN00000000000RE2", status_position=2000
        )

    def test_reorder_updates_positions(self):
        payload = [
            {"id": str(self.v1.id), "status_position": 2000},
            {"id": str(self.v2.id), "status_position": 1000},
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 2)
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.assertEqual(self.v1.status_position, 2000)
        self.assertEqual(self.v2.status_position, 1000)

    def test_reorder_with_status_change(self):
        payload = [
            {
                "id": str(self.v1.id),
                "status": VehicleStatus.READY,
                "status_position": 500,
            },
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.status, VehicleStatus.READY)
        self.assertEqual(self.v1.status_position, 500)

    def test_empty_array_returns_400(self):
        response = self.client.post(self.URL, [], format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_non_array_returns_400(self):
        response = self.client.post(self.URL, {"id": "abc"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_over_100_items_returns_400(self):
        items = [{"id": str(self.v1.id), "status_position": i} for i in range(101)]
        response = self.client.post(self.URL, items, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many", response.data["detail"])

    def test_archived_vehicles_skipped(self):
        self.v1.is_archived = True
        self.v1.save(update_fields=["is_archived"])
        payload = [
            {"id": str(self.v1.id), "status_position": 9999},
            {"id": str(self.v2.id), "status_position": 1000},
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 1)
        self.v1.refresh_from_db()
        self.assertNotEqual(self.v1.status_position, 9999)

    def test_nonexistent_vehicle_id_ignored(self):
        payload = [
            {"id": "00000000-0000-0000-0000-000000000000", "status_position": 100},
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 0)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.post(self.URL, [], format="json")
        self.assertEqual(response.status_code, 401)
