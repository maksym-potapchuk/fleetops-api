"""
Vehicle Driver Assignment Signal Tests
=======================================
Covers the full lifecycle of driver <-> vehicle signals:
- Assign driver on vehicle create
- Swap driver A → B
- Unassign driver (set to None)
- Driver with multiple vehicles — has_vehicle stays True
- Vehicle delete closes history
- VehicleDriverHistory consistency
"""

from django.test import TestCase

from driver.models import Driver
from vehicle.constants import ManufacturerChoices, VehicleStatus
from vehicle.models import Vehicle, VehicleDriverHistory


def make_driver(**kwargs):
    defaults = {
        "first_name": "Jan",
        "last_name": "Kowalski",
        "phone_number": "48123456789",
    }
    defaults.update(kwargs)
    return Driver.objects.create(**defaults)


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


class DriverAssignOnCreateTest(TestCase):
    """Signal: creating a vehicle with a driver pre-assigned."""

    def test_create_with_driver_creates_history(self):
        driver = make_driver()
        vehicle = make_vehicle(driver=driver)
        history = VehicleDriverHistory.objects.filter(vehicle=vehicle, driver=driver)
        self.assertEqual(history.count(), 1)
        self.assertIsNone(history.first().unassigned_at)

    def test_create_with_driver_sets_has_vehicle_true(self):
        driver = make_driver()
        make_vehicle(driver=driver)
        driver.refresh_from_db()
        self.assertTrue(driver.has_vehicle)

    def test_create_without_driver_creates_no_history(self):
        vehicle = make_vehicle()
        self.assertEqual(VehicleDriverHistory.objects.filter(vehicle=vehicle).count(), 0)


class DriverSwapTest(TestCase):
    """Signal: changing driver from A to B on existing vehicle."""

    def setUp(self):
        self.driver_a = make_driver(phone_number="48111111111")
        self.driver_b = make_driver(
            first_name="Anna", last_name="Nowak", phone_number="48222222222"
        )
        self.vehicle = make_vehicle(driver=self.driver_a)

    def test_swap_closes_old_history(self):
        self.vehicle.driver = self.driver_b
        self.vehicle.save()

        old_history = VehicleDriverHistory.objects.get(
            vehicle=self.vehicle, driver=self.driver_a
        )
        self.assertIsNotNone(old_history.unassigned_at)

    def test_swap_creates_new_history(self):
        self.vehicle.driver = self.driver_b
        self.vehicle.save()

        new_history = VehicleDriverHistory.objects.filter(
            vehicle=self.vehicle, driver=self.driver_b, unassigned_at__isnull=True
        )
        self.assertEqual(new_history.count(), 1)

    def test_swap_updates_has_vehicle_flags(self):
        self.vehicle.driver = self.driver_b
        self.vehicle.save()

        self.driver_a.refresh_from_db()
        self.driver_b.refresh_from_db()
        self.assertFalse(self.driver_a.has_vehicle)
        self.assertTrue(self.driver_b.has_vehicle)

    def test_total_history_records_after_swap(self):
        self.vehicle.driver = self.driver_b
        self.vehicle.save()
        self.assertEqual(
            VehicleDriverHistory.objects.filter(vehicle=self.vehicle).count(), 2
        )


class DriverUnassignTest(TestCase):
    """Signal: setting driver to None."""

    def test_unassign_closes_history(self):
        driver = make_driver()
        vehicle = make_vehicle(driver=driver)

        vehicle.driver = None
        vehicle.save()

        history = VehicleDriverHistory.objects.get(vehicle=vehicle, driver=driver)
        self.assertIsNotNone(history.unassigned_at)

    def test_unassign_sets_has_vehicle_false(self):
        driver = make_driver()
        vehicle = make_vehicle(driver=driver)

        vehicle.driver = None
        vehicle.save()

        driver.refresh_from_db()
        self.assertFalse(driver.has_vehicle)


class DriverMultipleVehiclesTest(TestCase):
    """Signal: driver assigned to 2 vehicles — unassign one should keep has_vehicle=True."""

    def test_unassign_one_of_two_keeps_has_vehicle_true(self):
        driver = make_driver()
        v1 = make_vehicle(driver=driver)
        v2 = make_vehicle(
            vin_number="2HGBH41JXMN109187",
            car_number="BB7702CC",
            driver=driver,
        )

        # Unassign from v1 only
        v1.driver = None
        v1.save()

        driver.refresh_from_db()
        self.assertTrue(
            driver.has_vehicle,
            "Driver still has v2 — has_vehicle must remain True",
        )

    def test_unassign_both_sets_has_vehicle_false(self):
        driver = make_driver()
        v1 = make_vehicle(driver=driver)
        v2 = make_vehicle(
            vin_number="2HGBH41JXMN109187",
            car_number="BB7702CC",
            driver=driver,
        )

        v1.driver = None
        v1.save()
        v2.driver = None
        v2.save()

        driver.refresh_from_db()
        self.assertFalse(driver.has_vehicle)


class VehicleDeleteSignalTest(TestCase):
    """Signal: deleting a vehicle should close driver history."""

    def test_delete_vehicle_closes_history(self):
        driver = make_driver()
        vehicle = make_vehicle(driver=driver)
        vehicle_id = vehicle.id

        vehicle.delete()

        # History should be cascade-deleted with the vehicle
        self.assertEqual(
            VehicleDriverHistory.objects.filter(vehicle_id=vehicle_id).count(), 0
        )

    def test_delete_vehicle_updates_has_vehicle(self):
        driver = make_driver()
        vehicle = make_vehicle(driver=driver)

        vehicle.delete()

        driver.refresh_from_db()
        self.assertFalse(driver.has_vehicle)
