"""
Notification Preferences Tests
===============================
Covers: GET/PATCH preferences, validation, defaults, regulation threshold.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from notification.models import NotificationPreferences
from notification.services import check_regulation_notifications

from .helpers import authenticate, make_regulation, make_user, make_vehicle

BASE_URL = "/api/v1/notifications/preferences/"


class PreferencesAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_get_creates_defaults_if_not_exists(self):
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["inspection_enabled"])
        self.assertTrue(response.data["regulation_enabled"])
        self.assertTrue(response.data["service_plan_enabled"])
        self.assertTrue(response.data["mileage_enabled"])
        self.assertEqual(response.data["inspection_notify_days"], [7, 3, 1])
        self.assertEqual(response.data["overdue_reminder_interval"], 7)
        self.assertEqual(response.data["overdue_reminder_max"], 3)
        self.assertEqual(response.data["regulation_notify_before_km"], 500)

    def test_patch_updates_fields(self):
        self.client.get(BASE_URL)  # ensure created
        response = self.client.patch(
            BASE_URL,
            {"inspection_enabled": False, "overdue_reminder_interval": 14},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["inspection_enabled"])
        self.assertEqual(response.data["overdue_reminder_interval"], 14)

    def test_patch_inspection_days_validates_list(self):
        self.client.get(BASE_URL)
        response = self.client.patch(
            BASE_URL,
            {"inspection_notify_days": "not a list"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_inspection_days_validates_range(self):
        self.client.get(BASE_URL)
        response = self.client.patch(
            BASE_URL,
            {"inspection_notify_days": [0, 100]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_inspection_days_sorts_and_deduplicates(self):
        self.client.get(BASE_URL)
        response = self.client.patch(
            BASE_URL,
            {"inspection_notify_days": [1, 7, 3, 7]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["inspection_notify_days"], [7, 3, 1])

    def test_patch_service_plan_days_validates_list(self):
        self.client.get(BASE_URL)
        response = self.client.patch(
            BASE_URL,
            {"service_plan_notify_days": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_service_plan_days_accepts_list(self):
        self.client.get(BASE_URL)
        response = self.client.patch(
            BASE_URL,
            {"service_plan_notify_days": [7, 3]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["service_plan_notify_days"], [7, 3])

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(BASE_URL)
        self.assertEqual(response.status_code, 401)


class RegulationThresholdTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(initial_km=9_700)
        self.schema, self.item, self.regulation, self.entry = make_regulation(
            self.vehicle,
            user=self.user,
            every_km=10_000,
            notify_before_km=500,
        )

    def test_uses_global_threshold_over_per_item(self):
        """Global regulation_notify_before_km overrides item's notify_before_km."""
        NotificationPreferences.objects.create(
            user=self.user,
            regulation_notify_before_km=1000,
        )
        # km_remaining = 10000 - 9700 = 300
        # Per-item threshold 500 → would notify
        # Global threshold 1000 → would also notify
        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 1)

    def test_global_threshold_below_remaining_skips(self):
        """No notification when remaining km exceeds global threshold."""
        NotificationPreferences.objects.create(
            user=self.user,
            regulation_notify_before_km=100,
        )
        # km_remaining = 300, threshold = 100 → skip
        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 0)

    def test_default_threshold_used_without_preferences(self):
        """Falls back to DEFAULT_REGULATION_NOTIFY_BEFORE_KM (500) when no prefs."""
        # km_remaining = 300 < 500 → notify
        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 1)
