"""
Vehicle Status History Tests
=============================
Covers: status history recording on creation, manual update, batch reorder,
        same-status no-op, and service function directly.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.constants import VehicleStatus
from vehicle.models import VehicleStatusHistory

from .helpers import authenticate, make_user, make_vehicle


class StatusHistoryOnCreateTest(TestCase):
    """POST /vehicle/ — creation records an initial CREATION entry."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        from fleet_management.models import EquipmentDefaultItem

        EquipmentDefaultItem.objects.all().delete()
        self.client = APIClient()
        self.user = make_user(email="create@example.com", username="createuser")
        authenticate(self.client, self.user)

    def test_create_records_initial_status(self):
        payload = {
            "model": "Camry",
            "manufacturer": "Toyota",
            "year": 2022,
            "cost": "25000.00",
            "vin_number": "VINHIST_CREATE001",
            "car_number": "HC0001AA",
            "color": "#000",
            "initial_km": 0,
            "status": "READY",
        }
        response = self.client.post(self.BASE_URL, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        vehicle_id = response.data["id"]
        entries = VehicleStatusHistory.objects.filter(vehicle_id=vehicle_id)
        self.assertEqual(entries.count(), 1)

        entry = entries.first()
        self.assertIsNone(entry.old_status)
        self.assertEqual(entry.new_status, "READY")
        self.assertEqual(entry.source, VehicleStatusHistory.ChangeSource.CREATION)
        self.assertEqual(entry.changed_by, self.user)


class StatusHistoryOnPatchTest(TestCase):
    """PATCH /vehicle/<id>/ — status change records a MANUAL entry."""

    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="patch@example.com", username="patchuser")
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(
            car_number="HP0001AA",
            vin_number="VIN_HIST_PATCH_001",
            status=VehicleStatus.AUCTION,
        )

    def test_patch_status_records_history(self):
        url = f"{self.BASE_URL}{self.vehicle.id}/"
        response = self.client.patch(url, {"status": "RENT"}, format="json")
        self.assertEqual(response.status_code, 200)

        entries = VehicleStatusHistory.objects.filter(vehicle=self.vehicle)
        self.assertEqual(entries.count(), 1)

        entry = entries.first()
        self.assertEqual(entry.old_status, "AUCTION")
        self.assertEqual(entry.new_status, "RENT")
        self.assertEqual(entry.source, VehicleStatusHistory.ChangeSource.MANUAL)
        self.assertEqual(entry.changed_by, self.user)

    def test_patch_same_status_does_not_record(self):
        url = f"{self.BASE_URL}{self.vehicle.id}/"
        response = self.client.patch(url, {"status": "AUCTION"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            VehicleStatusHistory.objects.filter(vehicle=self.vehicle).count(),
            0,
        )

    def test_patch_non_status_field_does_not_record(self):
        url = f"{self.BASE_URL}{self.vehicle.id}/"
        response = self.client.patch(url, {"color": "#FF0000"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            VehicleStatusHistory.objects.filter(vehicle=self.vehicle).count(),
            0,
        )


class StatusHistoryOnReorderTest(TestCase):
    """POST /vehicle/reorder/ — status change in batch records REORDER entries."""

    URL = "/api/v1/vehicle/reorder/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(
            email="reorder_hist@example.com", username="reordhistuser"
        )
        authenticate(self.client, self.user)
        self.v1 = make_vehicle(
            car_number="HR0001AA",
            vin_number="VIN_HIST_REORD_001",
            status=VehicleStatus.AUCTION,
            status_position=1000,
        )
        self.v2 = make_vehicle(
            car_number="HR0002AA",
            vin_number="VIN_HIST_REORD_002",
            status=VehicleStatus.SERVICE,
            status_position=2000,
        )

    def test_reorder_with_status_change_records_history(self):
        payload = [
            {
                "id": str(self.v1.id),
                "status": VehicleStatus.READY,
                "status_position": 500,
            },
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)

        entries = VehicleStatusHistory.objects.filter(vehicle=self.v1)
        self.assertEqual(entries.count(), 1)

        entry = entries.first()
        self.assertEqual(entry.old_status, "AUCTION")
        self.assertEqual(entry.new_status, "READY")
        self.assertEqual(entry.source, VehicleStatusHistory.ChangeSource.REORDER)

    def test_reorder_without_status_change_does_not_record(self):
        payload = [
            {"id": str(self.v1.id), "status_position": 3000},
            {"id": str(self.v2.id), "status_position": 4000},
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VehicleStatusHistory.objects.count(), 0)

    def test_reorder_multiple_status_changes_records_all(self):
        payload = [
            {
                "id": str(self.v1.id),
                "status": VehicleStatus.RENT,
                "status_position": 100,
            },
            {
                "id": str(self.v2.id),
                "status": VehicleStatus.SOLD,
                "status_position": 200,
            },
        ]
        response = self.client.post(self.URL, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VehicleStatusHistory.objects.count(), 2)


class RecordStatusChangeServiceTest(TestCase):
    """Direct unit tests for record_status_change service function."""

    def setUp(self):
        self.user = make_user(email="svc@example.com", username="svcuser")
        self.vehicle = make_vehicle(
            car_number="HS0001AA",
            vin_number="VIN_HIST_SVC_001",
            status=VehicleStatus.AUCTION,
        )

    def test_records_transition(self):
        from vehicle.services import record_status_change

        entry = record_status_change(
            self.vehicle,
            old_status="AUCTION",
            new_status="READY",
            user=self.user,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.old_status, "AUCTION")
        self.assertEqual(entry.new_status, "READY")
        self.assertEqual(entry.changed_by, self.user)

    def test_same_status_returns_none(self):
        from vehicle.services import record_status_change

        entry = record_status_change(
            self.vehicle,
            old_status="AUCTION",
            new_status="AUCTION",
            user=self.user,
        )
        self.assertIsNone(entry)
        self.assertEqual(VehicleStatusHistory.objects.count(), 0)
