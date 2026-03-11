"""
Notification API Tests
======================
Covers: list, unread-count, mark-read, read-all, resolve, mileage-submit.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from notification.constants import NotificationStatus, NotificationType
from notification.models import Notification

from .helpers import authenticate, make_driver, make_user, make_vehicle

BASE_URL = "/api/v1/notifications/"


class NotificationListTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle()

    def test_list_returns_paginated_results(self):
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE,
            vehicle=self.vehicle,
            payload={"item_title": "Oil Change"},
        )
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_type(self):
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE, vehicle=self.vehicle
        )
        Notification.objects.create(
            type=NotificationType.MILEAGE_SUBMITTED, vehicle=self.vehicle
        )
        response = self.client.get(BASE_URL, {"type": "regulation_overdue"})
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_is_read(self):
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE, is_read=False
        )
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE, is_read=True
        )
        response = self.client.get(BASE_URL, {"is_read": "false"})
        self.assertEqual(len(response.data["results"]), 1)

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(BASE_URL)
        self.assertEqual(response.status_code, 401)


class UnreadCountTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_returns_correct_count(self):
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE, is_read=False
        )
        Notification.objects.create(
            type=NotificationType.REGULATION_OVERDUE, is_read=True
        )
        response = self.client.get(f"{BASE_URL}unread-count/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)


class MarkReadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_marks_notification_as_read(self):
        n = Notification.objects.create(type=NotificationType.REGULATION_OVERDUE)
        response = self.client.patch(f"{BASE_URL}{n.id}/read/")
        self.assertEqual(response.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)


class MarkAllReadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)

    def test_marks_all_as_read(self):
        Notification.objects.create(type=NotificationType.REGULATION_OVERDUE)
        Notification.objects.create(type=NotificationType.MILEAGE_SUBMITTED)
        response = self.client.post(f"{BASE_URL}read-all/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)


class ResolveNotificationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(initial_km=10_000)
        self.driver = make_driver(telegram_id=12345)

    def test_approve_mileage_returns_200(self):
        n = Notification.objects.create(
            type=NotificationType.MILEAGE_SUBMITTED,
            status=NotificationStatus.PENDING,
            vehicle=self.vehicle,
            driver=self.driver,
            payload={"submitted_km": 12_000, "current_km": 10_000, "delta_km": 2_000},
        )
        response = self.client.patch(
            f"{BASE_URL}{n.id}/resolve/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")


class MileageSubmitTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        authenticate(self.client, self.user)
        self.vehicle = make_vehicle(initial_km=5_000)
        self.driver = make_driver(telegram_id=99999)

    def test_submit_creates_pending_notification(self):
        response = self.client.post(
            f"{BASE_URL}mileage-submit/",
            {
                "vehicle_id": str(self.vehicle.id),
                "km": 6000,
                "unit": "km",
                "driver_telegram_id": 99999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["type"], "mileage_submitted")
        self.assertEqual(response.data["status"], "pending")

    def test_submit_km_less_than_current_returns_400(self):
        response = self.client.post(
            f"{BASE_URL}mileage-submit/",
            {
                "vehicle_id": str(self.vehicle.id),
                "km": 3000,
                "unit": "km",
                "driver_telegram_id": 99999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_miles_converts_to_km(self):
        response = self.client.post(
            f"{BASE_URL}mileage-submit/",
            {
                "vehicle_id": str(self.vehicle.id),
                "km": 5000,
                "unit": "miles",
                "driver_telegram_id": 99999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertGreater(response.data["payload"]["submitted_km"], 5000)
