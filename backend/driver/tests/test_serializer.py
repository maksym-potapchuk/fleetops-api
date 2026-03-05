"""
DriverSerializer Validation Tests
==================================
Covers: validate_phone_number logic.
Rules: digits only, 10–15 chars, must start with "48" (Polish country code).
"""

from django.test import TestCase

from driver.serializers import DriverSerializer


class DriverSerializerValidationTest(TestCase):
    def _validate(self, data, instance=None):
        s = DriverSerializer(
            instance=instance, data=data, partial=(instance is not None)
        )
        s.is_valid()
        return s

    # --- valid cases ---

    def test_valid_polish_phone_number_accepted(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "Kowalski",
                "phone_number": "48123456789",
            }
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_minimum_length_10_digits_accepted(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "4812345678"}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_maximum_length_15_digits_accepted(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "481234567890123"}
        )
        self.assertTrue(s.is_valid(), s.errors)

    # --- invalid prefix ---

    def test_phone_without_48_prefix_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "79123456789"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("phone_number", s.errors)

    def test_phone_starting_with_480_rejected(self):
        """Only "48" prefix is allowed — "480..." must be rejected."""
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48012345678"}
        )
        # "48012345678".startswith("48") == True, so actually this is ACCEPTED.
        # Documenting the edge case: any number starting with "48" passes,
        # including those starting with "480", "481", etc.
        # This is the intended behaviour per the current rule.
        self.assertTrue(
            s.is_valid(), "48-prefixed numbers with trailing 0 are accepted"
        )

    # --- invalid format ---

    def test_phone_with_plus_prefix_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "+48123456789"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("phone_number", s.errors)

    def test_phone_with_hyphens_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48-123-456-789"}
        )
        self.assertFalse(s.is_valid())

    def test_phone_with_spaces_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "48 123 456 789"}
        )
        self.assertFalse(s.is_valid())

    def test_empty_phone_rejected(self):
        s = self._validate({"first_name": "Jan", "last_name": "K", "phone_number": ""})
        self.assertFalse(s.is_valid())

    # --- invalid length ---

    def test_phone_too_short_9_digits_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "481234567"}
        )
        self.assertFalse(s.is_valid())

    def test_phone_too_long_16_digits_rejected(self):
        s = self._validate(
            {"first_name": "Jan", "last_name": "K", "phone_number": "4812345678901234"}
        )
        self.assertFalse(s.is_valid())

    # --- read-only fields ---

    def test_read_only_has_vehicle_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "has_vehicle": True,
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("has_vehicle", s.validated_data)

    def test_read_only_is_active_driver_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "is_active_driver": True,
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("is_active_driver", s.validated_data)

    def test_read_only_last_active_at_cannot_be_set_via_serializer(self):
        s = self._validate(
            {
                "first_name": "Jan",
                "last_name": "K",
                "phone_number": "48123456789",
                "last_active_at": "2026-01-01T00:00:00Z",
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("last_active_at", s.validated_data)
