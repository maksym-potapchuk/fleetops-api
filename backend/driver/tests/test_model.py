"""
Driver Model Tests
==================
Covers: Driver model constraints, defaults, UUID id.
"""

import uuid

from django.db import IntegrityError
from django.test import TestCase

from .helpers import make_driver


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
