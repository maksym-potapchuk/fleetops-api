"""
Vehicle Owner Assignment Service Tests
=======================================
Covers: assign_owner, unassign_owner, multiple vehicles, archive behavior.
"""

from django.test import TestCase

from vehicle.models import OwnerHistory, VehicleOwner
from vehicle.services import assign_owner, unassign_owner

from .helpers import make_driver, make_vehicle


class AssignOwnerTest(TestCase):
    def test_assign_creates_vehicle_owner(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver)
        self.assertTrue(
            VehicleOwner.objects.filter(vehicle=vehicle, driver=driver).exists()
        )

    def test_assign_sets_has_vehicle_true(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver)
        driver.refresh_from_db()
        self.assertTrue(driver.has_vehicle)

    def test_assign_with_agreement_number(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver, agreement_number="AGR-001")
        owner = VehicleOwner.objects.get(vehicle=vehicle)
        self.assertEqual(owner.agreement_number, "AGR-001")


class SwapOwnerTest(TestCase):
    def setUp(self):
        self.driver_a = make_driver(phone_number="48111111111")
        self.driver_b = make_driver(
            first_name="Anna", last_name="Nowak", phone_number="48222222222"
        )
        self.vehicle = make_vehicle()
        assign_owner(self.vehicle, self.driver_a, agreement_number="OLD-AGR")

    def test_swap_archives_old_owner(self):
        assign_owner(self.vehicle, self.driver_b)
        history = OwnerHistory.objects.filter(
            vehicle=self.vehicle, driver=self.driver_a
        )
        self.assertEqual(history.count(), 1)
        self.assertIsNotNone(history.first().unassigned_at)
        self.assertEqual(history.first().agreement_number, "OLD-AGR")

    def test_swap_creates_new_owner(self):
        assign_owner(self.vehicle, self.driver_b)
        owner = VehicleOwner.objects.get(vehicle=self.vehicle)
        self.assertEqual(owner.driver, self.driver_b)

    def test_swap_updates_has_vehicle_flags(self):
        assign_owner(self.vehicle, self.driver_b)
        self.driver_a.refresh_from_db()
        self.driver_b.refresh_from_db()
        self.assertFalse(self.driver_a.has_vehicle)
        self.assertTrue(self.driver_b.has_vehicle)


class UnassignOwnerTest(TestCase):
    def test_unassign_archives_owner(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver)
        unassign_owner(vehicle)
        self.assertFalse(VehicleOwner.objects.filter(vehicle=vehicle).exists())
        self.assertEqual(OwnerHistory.objects.filter(vehicle=vehicle).count(), 1)

    def test_unassign_sets_has_vehicle_false(self):
        driver = make_driver()
        vehicle = make_vehicle()
        assign_owner(vehicle, driver)
        unassign_owner(vehicle)
        driver.refresh_from_db()
        self.assertFalse(driver.has_vehicle)

    def test_unassign_noop_when_no_owner(self):
        vehicle = make_vehicle()
        unassign_owner(vehicle)  # should not raise


class MultipleVehiclesTest(TestCase):
    def test_unassign_one_of_two_keeps_has_vehicle_true(self):
        driver = make_driver()
        v1 = make_vehicle()
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        assign_owner(v1, driver)
        assign_owner(v2, driver)

        unassign_owner(v1)
        driver.refresh_from_db()
        self.assertTrue(driver.has_vehicle)

    def test_unassign_both_sets_has_vehicle_false(self):
        driver = make_driver()
        v1 = make_vehicle()
        v2 = make_vehicle(vin_number="2HGBH41JXMN109187", car_number="BB7702CC")
        assign_owner(v1, driver)
        assign_owner(v2, driver)

        unassign_owner(v1)
        unassign_owner(v2)
        driver.refresh_from_db()
        self.assertFalse(driver.has_vehicle)
