"""
Vehicle API Tests
=================
Covers: CRUD operations, filters, unique constraints, auth guards.
"""

import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from driver.models import Driver
from vehicle.constants import ManufacturerChoices, VehicleStatus

from .helpers import authenticate, make_driver, make_user, make_vehicle


class VehicleAPITest(TestCase):
    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        from fleet_management.models import EquipmentDefaultItem

        # Migration 0005 seeds 7 default equipment items; clear them so
        # equipment-count assertions reflect only what this test creates.
        EquipmentDefaultItem.objects.all().delete()
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def _payload(self, **overrides):
        base = {
            "model": "Camry",
            "manufacturer": "Toyota",
            "year": 2022,
            "cost": "25000.00",
            "vin_number": "1HGBH41JXMN109186",
            "car_number": "AA6601BB",
            "color": "#FFFFFF",
            "initial_km": 0,
            "status": "AUCTION",
        }
        base.update(overrides)
        return base

    # --- create ---

    def test_create_vehicle_returns_201(self):
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)

    def test_created_vehicle_has_uuid_id(self):
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertIsNotNone(response.data.get("id"))

    def test_create_vehicle_auto_grants_default_equipment(self):
        from fleet_management.models import EquipmentDefaultItem, EquipmentList

        EquipmentDefaultItem.objects.create(equipment="Jack")
        EquipmentDefaultItem.objects.create(equipment="Spare Tire")
        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)
        count = EquipmentList.objects.filter(vehicle_id=response.data["id"]).count()
        self.assertEqual(count, 2, "Vehicle creation must auto-grant default equipment")

    def test_create_without_defaults_creates_no_equipment(self):
        from fleet_management.models import EquipmentList

        response = self.client.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 201)
        count = EquipmentList.objects.filter(vehicle_id=response.data["id"]).count()
        self.assertEqual(count, 0)

    def test_duplicate_vin_returns_400(self):
        make_vehicle()
        response = self.client.post(
            self.BASE_URL,
            self._payload(vin_number="1HGBH41JXMN109186", car_number="ZZ9999ZZ"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_car_number_returns_400(self):
        make_vehicle()
        response = self.client.post(
            self.BASE_URL,
            self._payload(vin_number="2HGBH41JXMN109187", car_number="AA6601BB"),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_manufacturer_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(
                manufacturer="UnknownBrand",
                vin_number="3HGBH41JXMN109188",
                car_number="CC8803DD",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_status_returns_400(self):
        response = self.client.post(
            self.BASE_URL,
            self._payload(
                status="FLYING",
                vin_number="4HGBH41JXMN109189",
                car_number="DD9904EE",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_year_is_rejected(self):
        """PositiveIntegerField — negative year values must not be accepted."""
        response = self.client.post(
            self.BASE_URL,
            self._payload(
                year=-1, vin_number="5HGBH41JXMN109190", car_number="EE0005FF"
            ),
            format="json",
        )
        self.assertNotEqual(response.status_code, 201)

    # --- list ---

    def test_list_returns_200(self):
        make_vehicle()
        response = self.client.get(self.BASE_URL)
        self.assertEqual(response.status_code, 200)

    def test_list_filters_by_status(self):
        make_vehicle(status=VehicleStatus.READY)
        make_vehicle(
            vin_number="2HGBH41JXMN109187",
            car_number="BB7702CC",
            status=VehicleStatus.SOLD,
        )
        response = self.client.get(self.BASE_URL + "?status=READY")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], "READY")

    def test_list_filters_by_manufacturer(self):
        make_vehicle(
            manufacturer=ManufacturerChoices.BMW,
            vin_number="BVIN001",
            car_number="BMW001",
        )
        make_vehicle(
            manufacturer=ManufacturerChoices.AUDI,
            vin_number="AVIN001",
            car_number="AUDI001",
        )
        response = self.client.get(self.BASE_URL + "?manufacturer=BMW")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    # --- retrieve ---

    def test_retrieve_existing_vehicle_returns_200(self):
        vehicle = make_vehicle()
        response = self.client.get(f"{self.BASE_URL}{vehicle.id}/")
        self.assertEqual(response.status_code, 200)

    def test_retrieve_nonexistent_vehicle_returns_404(self):
        response = self.client.get(f"{self.BASE_URL}{uuid.uuid4()}/")
        self.assertEqual(response.status_code, 404)

    # --- update ---

    def test_patch_status_updates_successfully(self):
        vehicle = make_vehicle()
        response = self.client.patch(
            f"{self.BASE_URL}{vehicle.id}/", {"status": "READY"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, "READY")

    def test_patch_vin_to_existing_value_returns_400(self):
        v1 = make_vehicle()
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        response = self.client.patch(
            f"{self.BASE_URL}{v2.id}/",
            {"vin_number": v1.vin_number},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- delete ---

    def test_delete_vehicle_without_driver_archives_it(self):
        vehicle = make_vehicle()
        response = self.client.delete(f"{self.BASE_URL}{vehicle.id}/")
        self.assertEqual(response.status_code, 204)
        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_archived)
        self.assertIsNotNone(vehicle.archived_at)

    def test_deleting_vehicle_with_owner_does_not_delete_driver(self):
        """Vehicle archiving should NOT delete the assigned driver."""
        from vehicle.models import VehicleOwner

        driver = make_driver()
        vehicle = make_vehicle()
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)

        self.client.delete(f"{self.BASE_URL}{vehicle.id}/")
        self.assertTrue(Driver.objects.filter(id=driver.id).exists())

    # --- authentication ---

    def test_unauthenticated_list_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(self.BASE_URL)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_create_returns_401(self):
        unauthenticated = APIClient()
        response = unauthenticated.post(self.BASE_URL, self._payload(), format="json")
        self.assertEqual(response.status_code, 401)
