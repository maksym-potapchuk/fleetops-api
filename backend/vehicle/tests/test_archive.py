"""
Vehicle Archive / Restore / Permanent Delete API Tests
=======================================================
"""

from django.test import TestCase
from rest_framework.test import APIClient

from vehicle.models import OwnerHistory, VehicleOwner
from vehicle.services import assign_owner

from .helpers import authenticate, make_driver, make_user, make_vehicle


class VehicleArchiveTest(TestCase):
    BASE_URL = "/api/v1/vehicle/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user(email="archive@example.com", username="archuser")
        authenticate(self.client, self.user)

    def test_delete_archives_vehicle_instead_of_hard_delete(self):
        vehicle = make_vehicle()
        response = self.client.delete(f"{self.BASE_URL}{vehicle.id}/")
        self.assertEqual(response.status_code, 204)
        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_archived)
        self.assertIsNotNone(vehicle.archived_at)

    def test_archived_vehicle_excluded_from_list(self):
        v1 = make_vehicle(car_number="ACTIVE01", vin_number="VIN00000000000001")
        v2 = make_vehicle(car_number="ARCHIV01", vin_number="VIN00000000000002")
        v2.is_archived = True
        v2.save(update_fields=["is_archived"])

        response = self.client.get(self.BASE_URL)
        self.assertEqual(response.status_code, 200)
        ids = [v["id"] for v in response.data["results"]]
        self.assertIn(str(v1.id), ids)
        self.assertNotIn(str(v2.id), ids)

    def test_archive_unassigns_owner(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver)

        self.client.delete(f"{self.BASE_URL}{vehicle.id}/")

        vehicle.refresh_from_db()
        self.assertTrue(vehicle.is_archived)
        self.assertFalse(VehicleOwner.objects.filter(vehicle=vehicle).exists())
        self.assertEqual(OwnerHistory.objects.filter(vehicle=vehicle).count(), 1)

    def test_archive_list_returns_only_archived(self):
        make_vehicle(car_number="ACTIVE02", vin_number="VIN00000000000003")
        archived = make_vehicle(car_number="ARCHIV02", vin_number="VIN00000000000004")
        archived.is_archived = True
        archived.save(update_fields=["is_archived"])

        response = self.client.get(f"{self.BASE_URL}archive/")
        self.assertEqual(response.status_code, 200)
        ids = [v["id"] for v in response.data["results"]]
        self.assertEqual(len(ids), 1)
        self.assertIn(str(archived.id), ids)

    def test_restore_sets_is_archived_false(self):
        vehicle = make_vehicle()
        vehicle.is_archived = True
        vehicle.save(update_fields=["is_archived"])

        response = self.client.post(f"{self.BASE_URL}{vehicle.id}/restore/")
        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertFalse(vehicle.is_archived)
        self.assertIsNone(vehicle.archived_at)

    def test_permanent_delete_clean_vehicle(self):
        vehicle = make_vehicle()
        vehicle.is_archived = True
        vehicle.save(update_fields=["is_archived"])
        vehicle_id = vehicle.id

        response = self.client.delete(f"{self.BASE_URL}{vehicle_id}/permanent-delete/")
        self.assertEqual(response.status_code, 204)
        from vehicle.models import Vehicle

        self.assertFalse(Vehicle.objects.filter(pk=vehicle_id).exists())

    def test_permanent_delete_with_data_requires_confirm(self):
        vehicle = make_vehicle()
        vehicle.is_archived = True
        vehicle.save(update_fields=["is_archived"])
        driver = make_driver(phone_number="48999888777")
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)

        response = self.client.delete(f"{self.BASE_URL}{vehicle.id}/permanent-delete/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data["has_related_data"])

    def test_permanent_delete_with_confirm_deletes(self):
        vehicle = make_vehicle()
        vehicle.is_archived = True
        vehicle.save(update_fields=["is_archived"])
        driver = make_driver(phone_number="48777666555")
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)
        vehicle_id = vehicle.id

        response = self.client.delete(
            f"{self.BASE_URL}{vehicle_id}/permanent-delete/?confirm=true"
        )
        self.assertEqual(response.status_code, 204)
        from vehicle.models import Vehicle

        self.assertFalse(Vehicle.objects.filter(pk=vehicle_id).exists())

    def test_delete_check_returns_related_counts(self):
        vehicle = make_vehicle()
        vehicle.is_archived = True
        vehicle.save(update_fields=["is_archived"])
        driver = make_driver(phone_number="48555444333")
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)

        response = self.client.get(f"{self.BASE_URL}{vehicle.id}/delete-check/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_related_data"])
        self.assertEqual(response.data["related_counts"]["current_owner"], 1)
