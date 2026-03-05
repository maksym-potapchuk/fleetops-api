"""
Vehicle Model Tests
===================
Covers: Vehicle model, VehicleOwner model.

BUG / VULNERABILITY markers document known flaws that tests expose.
"""

import uuid

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from vehicle.constants import VehicleStatus
from vehicle.models import Vehicle, VehicleOwner

from .helpers import make_driver, make_vehicle

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

    def test_default_status_is_auction(self):
        vehicle = make_vehicle()
        self.assertEqual(vehicle.status, VehicleStatus.AUCTION)

    def test_default_is_selected_is_true(self):
        vehicle = make_vehicle()
        self.assertTrue(vehicle.is_selected)

    def test_default_initial_km_is_zero(self):
        vehicle = make_vehicle()
        self.assertEqual(vehicle.initial_km, 0)

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

    def test_owner_protect_prevents_driver_deletion(self):
        """
        VehicleOwner.driver is FK to Driver with on_delete=PROTECT.
        A driver assigned as owner cannot be deleted.
        """
        driver = make_driver()
        vehicle = make_vehicle()
        VehicleOwner.objects.create(vehicle=vehicle, driver=driver)

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
