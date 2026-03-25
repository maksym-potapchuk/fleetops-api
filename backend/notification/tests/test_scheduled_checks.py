"""
Scheduled Notification Checks Tests
====================================
Covers: check_inspection_notifications, check_service_plan_notifications,
        overdue reminders, preferences integration.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from fleet_management.models import ServicePlan
from notification.constants import NotificationType
from notification.models import Notification, NotificationPreferences
from notification.services import (
    check_all_scheduled_notifications,
    check_inspection_notifications,
    check_service_plan_notifications,
)
from vehicle.models import TechnicalInspection

from .helpers import make_user, make_vehicle


class CheckInspectionNotificationsTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def _create_inspection(self, next_date):
        return TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date.today() - timedelta(days=365),
            next_inspection_date=next_date,
            created_by=self.user,
        )

    def test_creates_expiring_notification_at_threshold(self):
        self._create_inspection(date.today() + timedelta(days=3))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.INSPECTION_EXPIRING)
        self.assertEqual(created[0].payload["days_remaining"], 3)

    def test_creates_expired_notification_when_overdue(self):
        self._create_inspection(date.today() - timedelta(days=5))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.INSPECTION_EXPIRED)
        self.assertEqual(created[0].payload["overdue_days"], 5)

    def test_no_notification_outside_threshold(self):
        self._create_inspection(date.today() + timedelta(days=15))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)

    def test_skips_archived_vehicles(self):
        self.vehicle.is_archived = True
        self.vehicle.save(update_fields=["is_archived"])
        self._create_inspection(date.today() + timedelta(days=3))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)

    def test_skips_sold_vehicles(self):
        self.vehicle.status = "SOLD"
        self.vehicle.save(update_fields=["status"])
        self._create_inspection(date.today() + timedelta(days=3))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)

    def test_deduplicates_expiring(self):
        self._create_inspection(date.today() + timedelta(days=3))
        check_inspection_notifications()
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_respects_disabled_preference(self):
        NotificationPreferences.objects.create(
            user=self.user,
            inspection_enabled=False,
        )
        self._create_inspection(date.today() + timedelta(days=3))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)

    def test_respects_custom_threshold_days(self):
        NotificationPreferences.objects.create(
            user=self.user,
            inspection_notify_days=[14, 5],
        )
        self._create_inspection(date.today() + timedelta(days=5))
        created = check_inspection_notifications()
        self.assertEqual(len(created), 1)


class CheckServicePlanNotificationsTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def _create_plan(self, planned_at, title="Brake check"):
        return ServicePlan.objects.create(
            vehicle=self.vehicle,
            title=title,
            planned_at=planned_at,
            created_by=self.user,
        )

    def test_creates_due_notification_at_threshold(self):
        NotificationPreferences.objects.create(
            user=self.user,
            service_plan_notify_days=[3, 1],
        )
        self._create_plan(date.today() + timedelta(days=3))
        created = check_service_plan_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.SERVICE_PLAN_DUE)

    def test_creates_overdue_notification(self):
        self._create_plan(date.today() - timedelta(days=2))
        created = check_service_plan_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].type, NotificationType.SERVICE_PLAN_OVERDUE)
        self.assertEqual(created[0].payload["overdue_days"], 2)

    def test_skips_done_plans(self):
        plan = self._create_plan(date.today() - timedelta(days=2))
        plan.is_done = True
        plan.save(update_fields=["is_done"])
        created = check_service_plan_notifications()
        self.assertEqual(len(created), 0)

    def test_no_notification_outside_threshold(self):
        NotificationPreferences.objects.create(
            user=self.user,
            service_plan_notify_days=[3],
        )
        self._create_plan(date.today() + timedelta(days=10))
        created = check_service_plan_notifications()
        self.assertEqual(len(created), 0)


class OverdueRemindersTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def _create_inspection(self, overdue_days):
        return TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date.today() - timedelta(days=365),
            next_inspection_date=date.today() - timedelta(days=overdue_days),
            created_by=self.user,
        )

    def test_first_overdue_always_sent(self):
        self._create_inspection(overdue_days=1)
        created = check_inspection_notifications()
        self.assertEqual(len(created), 1)

    def test_second_reminder_not_sent_before_interval(self):
        NotificationPreferences.objects.create(
            user=self.user,
            overdue_reminder_interval=7,
            overdue_reminder_max=3,
        )
        self._create_inspection(overdue_days=3)
        check_inspection_notifications()
        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)

    def test_second_reminder_sent_after_interval(self):
        NotificationPreferences.objects.create(
            user=self.user,
            overdue_reminder_interval=7,
            overdue_reminder_max=3,
        )
        self._create_inspection(overdue_days=10)
        check_inspection_notifications()

        # Backdate first notification to 8 days ago
        n = Notification.objects.first()
        Notification.objects.filter(pk=n.pk).update(
            created_at=timezone.now() - timedelta(days=8),
        )

        created = check_inspection_notifications()
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].payload["reminder_number"], 1)

    def test_stops_after_max_reminders(self):
        NotificationPreferences.objects.create(
            user=self.user,
            overdue_reminder_interval=1,
            overdue_reminder_max=2,
        )
        self._create_inspection(overdue_days=30)

        # Create 2 existing reminders
        for i in range(2):
            Notification.objects.create(
                type=NotificationType.INSPECTION_EXPIRED,
                vehicle=self.vehicle,
                dedup_key=f"inspection_expired:{self.vehicle.pk}:{TechnicalInspection.objects.first().pk}:r{i}",
                payload={"reminder_number": i},
            )

        created = check_inspection_notifications()
        self.assertEqual(len(created), 0)


class CheckAllScheduledTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.vehicle = make_vehicle()

    def test_returns_counts(self):
        TechnicalInspection.objects.create(
            vehicle=self.vehicle,
            inspection_date=date.today() - timedelta(days=365),
            next_inspection_date=date.today() + timedelta(days=3),
            created_by=self.user,
        )
        result = check_all_scheduled_notifications()
        self.assertIn("inspections", result)
        self.assertIn("service_plans", result)
        self.assertEqual(result["inspections"], 1)
