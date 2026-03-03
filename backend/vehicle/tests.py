"""
Vehicle Test Suite
==================
Covers: Vehicle model, VehicleDriverHistory model, Vehicle API endpoints.

BUG / VULNERABILITY markers document known flaws that tests expose.
"""

import uuid

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User
from driver.models import Driver
from vehicle.models import (
    ManufacturerChoices,
    Vehicle,
    VehicleDriverHistory,
    VehicleStatus,
)

# ---------------------------------------------------------------------------
# Shared factory helpers
# ---------------------------------------------------------------------------


def make_user(email="test@example.com", password="pass123!", username="testuser"):
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


# ===========================================================================
# 1. Vehicle Model Tests
# ===========================================================================


class VehicleModelTest(TestCase):
    def test_vin_number_unique_constraint(self):
        make_vehicle()
        with self.assertRaises(IntegrityError):
            make_vehicle(car_number="BB7702CC")  # same vin, different car_number

    def test_car_number_unique_constraint(self):
        make_vehicle()
        with self.assertRaises(IntegrityError):
            make_vehicle(
                vin_number="2HGBH41JXMN109187"
            )  # different vin, same car_number

    def test_default_status_is_preparation(self):
        vehicle = make_vehicle()
        self.assertEqual(vehicle.status, VehicleStatus.PREPARATION)

    def test_default_is_selected_is_true(self):
        vehicle = make_vehicle()
        self.assertTrue(vehicle.is_selected)

    def test_default_initial_km_is_zero(self):
        vehicle = make_vehicle()
        self.assertEqual(vehicle.initial_km, 0)

    def test_driver_fk_is_nullable(self):
        vehicle = make_vehicle()
        self.assertIsNone(vehicle.driver)

    def test_str_representation(self):
        vehicle = make_vehicle()
        self.assertEqual(str(vehicle), "AA6601BB (Toyota Camry)")

    def test_vehicle_id_is_uuid(self):
        vehicle = make_vehicle()
        self.assertIsInstance(vehicle.id, uuid.UUID)

    def test_manufacturer_choices_not_enforced_at_db_level(self):
        """
        VULNERABILITY: Django TextChoices are NOT enforced at the database level.
        An arbitrary manufacturer value can be stored directly via ORM, bypassing
        the serializer's choice validation.
        """
        vehicle = Vehicle.objects.create(
            model="Unknown",
            manufacturer="UnknownBrand",  # not in ManufacturerChoices
            year=2022,
            cost="10000.00",
            vin_number="BADVIN00000000001",
            car_number="BAD001",
            color="#000000",
            initial_km=0,
        )
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.manufacturer, "UnknownBrand")

    def test_all_valid_statuses_can_be_saved(self):
        valid_statuses = [s.value for s in VehicleStatus]
        for i, status in enumerate(valid_statuses):
            make_vehicle(
                vin_number=f"VIN{i:014d}",
                car_number=f"S{i:05d}",
                status=status,
            )
        self.assertEqual(Vehicle.objects.count(), len(valid_statuses))

    def test_driver_protect_prevents_driver_deletion_when_vehicle_assigned(self):
        """
        Vehicle.driver is FK to Driver with on_delete=PROTECT.
        A driver assigned to a vehicle cannot be deleted.
        """
        driver = make_driver()
        vehicle = make_vehicle()
        vehicle.driver = driver
        vehicle.save()

        with self.assertRaises(ProtectedError):
            driver.delete()

    def test_vehicle_deletion_cascades_to_regulations(self):
        from fleet_management.models import (
            FleetVehicleRegulation,
            FleetVehicleRegulationSchema,
        )

        schema = FleetVehicleRegulationSchema.objects.create(title="Test")
        vehicle = make_vehicle()
        FleetVehicleRegulation.objects.create(vehicle=vehicle, schema=schema)
        vehicle.delete()
        self.assertEqual(
            FleetVehicleRegulation.objects.filter(schema=schema).count(),
            0,
            "FleetVehicleRegulation must be cascade-deleted with the vehicle",
        )

    def test_vehicle_deletion_cascades_to_equipment_list(self):
        from fleet_management.models import EquipmentList

        vehicle = make_vehicle()
        EquipmentList.objects.create(vehicle=vehicle, equipment="Jack")
        vehicle.delete()
        self.assertEqual(EquipmentList.objects.count(), 0)

    def test_vehicle_deletion_cascades_to_service_plans(self):
        from datetime import date

        from fleet_management.models import ServicePlan

        vehicle = make_vehicle()
        ServicePlan.objects.create(
            vehicle=vehicle, title="Plan", planned_at=date.today()
        )
        vehicle.delete()
        self.assertEqual(ServicePlan.objects.count(), 0)


# ===========================================================================
# 2. VehicleDriverHistory Model Tests
# ===========================================================================


class VehicleDriverHistoryModelTest(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle()
        self.driver = make_driver()

    def test_creates_history_record_successfully(self):
        history = VehicleDriverHistory.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
        )
        self.assertIsNotNone(history.id)
        self.assertIsNone(history.unassigned_at)

    def test_assigned_at_is_set_automatically(self):
        history = VehicleDriverHistory.objects.create(
            vehicle=self.vehicle, driver=self.driver
        )
        self.assertIsNotNone(history.assigned_at)

    def test_no_constraint_prevents_multiple_open_assignments(self):
        """
        VULNERABILITY: No unique constraint or model validation prevents multiple
        open (unassigned_at=None) assignments for the same vehicle+driver pair.
        This can cause data inconsistency — e.g. two open history rows for one pair.
        """
        VehicleDriverHistory.objects.create(vehicle=self.vehicle, driver=self.driver)
        history2 = VehicleDriverHistory.objects.create(
            vehicle=self.vehicle, driver=self.driver
        )
        self.assertIsNotNone(
            history2.id,
            "VULNERABILITY CONFIRMED: multiple open assignments allowed without error",
        )
        open_count = VehicleDriverHistory.objects.filter(
            vehicle=self.vehicle,
            driver=self.driver,
            unassigned_at=None,
        ).count()
        self.assertEqual(open_count, 2)

    def test_driver_has_vehicle_flag_auto_updated_on_assignment(self):
        """
        vehicle/signals.py post_save handler auto-updates Driver.has_vehicle
        whenever Vehicle.driver FK changes. Assigning a vehicle must flip the
        flag to True without any manual call.
        """
        self.vehicle.driver = self.driver
        self.vehicle.save()

        self.driver.refresh_from_db()
        self.assertTrue(
            self.driver.has_vehicle,
            "Driver.has_vehicle must be True after vehicle is assigned via signal",
        )

    def test_str_representation_contains_vehicle_and_driver(self):
        history = VehicleDriverHistory.objects.create(
            vehicle=self.vehicle, driver=self.driver
        )
        self.assertIn("AA6601BB", str(history))
        self.assertIn("Jan Kowalski", str(history))


# ===========================================================================
# 3. Vehicle API Tests
# ===========================================================================


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
            "status": "PREPARATION",
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

    def test_deleting_vehicle_with_driver_does_not_delete_driver(self):
        """Vehicle archiving should NOT delete the assigned driver."""
        driver = make_driver()
        vehicle = make_vehicle()
        vehicle.driver = driver
        vehicle.save()

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
