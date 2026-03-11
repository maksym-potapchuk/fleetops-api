"""
Notification Services Tests
============================
Covers: create_notification, check_regulation_notifications, resolve_notification.
"""

from django.test import TestCase

from notification.constants import NotificationStatus, NotificationType
from notification.models import Notification
from notification.services import (
    check_regulation_notifications,
    create_notification,
    resolve_notification,
)

from .helpers import make_driver, make_regulation, make_user, make_vehicle


class CreateNotificationTest(TestCase):
    def setUp(self):
        self.vehicle = make_vehicle()
        self.driver = make_driver()

    def test_creates_notification_with_correct_fields(self):
        n = create_notification(
            notification_type=NotificationType.MILEAGE_SUBMITTED,
            vehicle=self.vehicle,
            driver=self.driver,
            status=NotificationStatus.PENDING,
            payload={"submitted_km": 5000},
            push=False,
        )
        self.assertEqual(n.type, NotificationType.MILEAGE_SUBMITTED)
        self.assertEqual(n.status, NotificationStatus.PENDING)
        self.assertEqual(n.vehicle, self.vehicle)
        self.assertEqual(n.driver, self.driver)
        self.assertEqual(n.payload["submitted_km"], 5000)
        self.assertFalse(n.is_read)

    def test_defaults_to_info_status(self):
        n = create_notification(
            notification_type=NotificationType.REGULATION_OVERDUE,
            push=False,
        )
        self.assertEqual(n.status, NotificationStatus.INFO)


class CheckRegulationNotificationsTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(initial_km=0)
        self.schema, self.item, self.regulation, self.entry = make_regulation(
            self.vehicle, user=self.user, every_km=10_000, notify_before_km=500
        )

    def test_creates_overdue_notification(self):
        """When current_km >= next_due_km, create REGULATION_OVERDUE."""
        self.vehicle.initial_km = 10_500
        self.vehicle.save(update_fields=["initial_km"])

        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.REGULATION_OVERDUE)
        self.assertEqual(created[0].payload["overdue_by_km"], 500)

    def test_creates_approaching_notification(self):
        """When km_remaining <= notify_before_km, create REGULATION_APPROACHING."""
        self.vehicle.initial_km = 9_600
        self.vehicle.save(update_fields=["initial_km"])

        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.REGULATION_APPROACHING)
        self.assertEqual(created[0].payload["km_remaining"], 400)

    def test_no_notification_when_not_due(self):
        """When km_remaining > notify_before_km, no notification created."""
        self.vehicle.initial_km = 5_000
        self.vehicle.save(update_fields=["initial_km"])

        created = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created), 0)

    def test_deduplicates_unread_notifications(self):
        """Does not create duplicate if unread notification for same entry+type exists."""
        self.vehicle.initial_km = 10_500
        self.vehicle.save(update_fields=["initial_km"])

        check_regulation_notifications(self.vehicle)
        created_second = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created_second), 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_creates_new_after_read(self):
        """Creates new notification if previous one was marked as read."""
        self.vehicle.initial_km = 10_500
        self.vehicle.save(update_fields=["initial_km"])

        created = check_regulation_notifications(self.vehicle)
        created[0].is_read = True
        created[0].save(update_fields=["is_read"])

        created_again = check_regulation_notifications(self.vehicle)
        self.assertEqual(len(created_again), 1)
        self.assertEqual(Notification.objects.count(), 2)


class ResolveNotificationTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle(initial_km=10_000)
        self.driver = make_driver(telegram_id=12345)

    def test_approve_mileage_creates_log_and_updates_km(self):
        """Approving mileage notification creates MileageLog and updates vehicle.initial_km."""
        from vehicle.models import MileageLog

        n = create_notification(
            notification_type=NotificationType.MILEAGE_SUBMITTED,
            vehicle=self.vehicle,
            driver=self.driver,
            status=NotificationStatus.PENDING,
            payload={
                "submitted_km": 12_000,
                "current_km": 10_000,
                "delta_km": 2_000,
                "unit": "km",
                "source": "telegram_bot",
            },
            push=False,
        )

        resolved = resolve_notification(n, "approve", self.user)
        self.assertEqual(resolved.status, NotificationStatus.APPROVED)
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(resolved.resolved_by, self.user)

        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.initial_km, 12_000)
        self.assertEqual(MileageLog.objects.count(), 1)

    def test_reject_sets_status_without_side_effects(self):
        from vehicle.models import MileageLog

        n = create_notification(
            notification_type=NotificationType.MILEAGE_SUBMITTED,
            vehicle=self.vehicle,
            driver=self.driver,
            status=NotificationStatus.PENDING,
            payload={"submitted_km": 12_000, "current_km": 10_000},
            push=False,
        )

        resolved = resolve_notification(n, "reject", self.user)
        self.assertEqual(resolved.status, NotificationStatus.REJECTED)

        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.initial_km, 10_000)
        self.assertEqual(MileageLog.objects.count(), 0)

    def test_resolve_non_pending_raises_error(self):
        n = create_notification(
            notification_type=NotificationType.REGULATION_OVERDUE,
            status=NotificationStatus.INFO,
            push=False,
        )
        with self.assertRaises(ValueError):
            resolve_notification(n, "approve", self.user)
